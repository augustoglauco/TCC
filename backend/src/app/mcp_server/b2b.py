"""Servidor MCP B2B provido pela empresa (R12, Fase 5) — expõe os 4 recursos
de leitura e as 4 ferramentas transacionais descritos em
`docs/ARCHITECTURE.md` §6: catálogo, estoque, tabela de preços e
manuais/documentação (recursos); validação de compatibilidade, consulta de
frete e prazos, cotação automática e reserva/pedido (ferramentas).

Reaproveita o "backend único de dados" já modelado no item anterior desta
fase (`app.db.catalog`, sobre `Produto`/`ProdutoEstoque`/
`ProdutoDescontoVolume`/`ProdutoCompatibilidade`/`Pedido`/`PedidoItem`) para
os recursos/ferramentas estruturados, e a infraestrutura RAG já existente
(`app.rag.qdrant_client`) para o recurso de manuais — o parceiro B2B busca
tanto nas collections `purpose="mcp_b2b"` quanto na collection ativa
`purpose="chat"` (mesmo conteúdo que o chat público usa); só o caminho
inverso é bloqueado (o chat público nunca busca `purpose="mcp_b2b"`, ver
decisão de 2026-09-30 em `docs/ARCHITECTURE.md` §6).

# MVP: exposto publicamente (via Caddy/HTTPS) só com chave estática por
parceiro (`app.mcp_server.auth`), sem OAuth, escopos nem rate limiting — ver
decisão de 2026-09-25 em `docs/ARCHITECTURE.md` §6. Cada chamada de
ferramenta gera o log `mcp_b2b_ferramenta` com o parceiro que chamou.

Modelado como *MCP resources* os quatro itens de dados somente-leitura,
endereçáveis por URI (`catalogo://`, `estoque://`, `precos://`,
`manuais://`), e como *MCP tools* as quatro ferramentas transacionais
(`validar_compatibilidade`, `consultar_frete`, `cotar`, `reservar_pedido`) —
o protocolo MCP reserva "tools" para ações/automações (ver "Recursos" vs
"Ferramentas" em `docs/ARCHITECTURE.md` §6). Erros anticipados de tool usam
`ToolError` (equivalente a `ResourceError` do lado dos resources, ver
`mcp.server.mcpserver.exceptions`) — o SDK também levanta `ToolError`
automaticamente quando os argumentos falham a validação Pydantic do input
schema da tool (ex.: `quantidade` sem ser `> 0`), sem precisar de tratamento
explícito aqui.

SDK: `mcp` (Python SDK oficial), interface `mcp.server.mcpserver.MCPServer`
— nesta versão instalada do pacote (2.x), a antiga `FastMCP` foi renomeada
para `MCPServer` (ver `pyproject.toml`, `mcp>=2.0`).
"""

from __future__ import annotations

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError, ToolError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.catalog import (
    EstoqueInsuficienteError,
    ProdutoInexistenteError,
    calcular_item_cotacao,
    criar_pedido,
    listar_estoque,
    listar_produtos,
    obter_produto,
    obter_produtos_por_ids,
    sao_compativeis,
)
from app.db.models import Produto
from app.mcp_server.auth import parceiro_atual
from app.models.mcp_b2b import (
    CatalogoProdutoOut,
    CompatibilidadeOut,
    CotacaoItemIn,
    CotacaoItemOut,
    CotacaoOut,
    DescontoVolumeOut,
    EstoqueCentroOut,
    EstoqueProdutoOut,
    FreteItemIn,
    FreteOut,
    ItemQuantidadeIn,
    ManualBuscaOut,
    ManualResultadoOut,
    PedidoItemIn,
    PedidoOut,
    PrecoProdutoOut,
)
from app.rag.collections_registry import list_collections
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.multi_collection_search import buscar_em_varias_collections
from app.rag.qdrant_client import QdrantRAGClient

logger = logging.getLogger(__name__)

# MVP: pool de resultados por collection mcp_b2b consultada, sem reranking
# entre collections além da ordenação por score — suficiente para a base
# pequena deste protótipo (ver docs/ARCHITECTURE.md §6, "Escopo no
# protótipo").
DEFAULT_MANUAIS_TOP_K = 5

# Ferramenta 2 (consulta de frete e prazos): estimativa determinística
# interna a partir do primeiro dígito do CEP (região dos Correios, 0-9) —
# tabela fixa de custo-base/prazo por região + um adicional por kg, todos
# constantes deste módulo (não um domínio de configuração via admin, fora do
# escopo deste item). `# MVP: estimativa, não frete real — nenhuma
# transportadora é consultada` (ver docs/ARCHITECTURE.md §5, decisão de
# 2026-09-24).
_FRETE_CUSTO_BASE_E_PRAZO_POR_REGIAO: dict[str, tuple[Decimal, int]] = {
    "0": (Decimal("35.00"), 2),  # SP capital/região metropolitana
    "1": (Decimal("40.00"), 3),  # interior de SP
    "2": (Decimal("45.00"), 3),  # RJ/ES
    "3": (Decimal("45.00"), 3),  # MG
    "4": (Decimal("55.00"), 5),  # BA/SE
    "5": (Decimal("60.00"), 5),  # PE/AL/PB/RN
    "6": (Decimal("70.00"), 7),  # CE/PI/MA/PA/AM/AP/RR/AC/RO
    "7": (Decimal("50.00"), 4),  # DF/GO/TO/MT/MS
    "8": (Decimal("55.00"), 4),  # PR/SC
    "9": (Decimal("50.00"), 4),  # RS
}
_FRETE_ADICIONAL_POR_KG = Decimal("2.50")


# Endereços que só aceitam conexão da própria máquina.
_HOSTS_SOMENTE_LOCAL = frozenset({"127.0.0.1", "localhost", "::1"})


def host_somente_local(host: str) -> bool:
    """`True` se o servidor, escutando em `host`, só aceita conexões da
    própria máquina. `scripts/run_mcp_b2b_server.py` avisa no log quando não
    é o caso, porque o MCP B2B não tem autenticação por parceiro (MVP)."""
    return host.strip().lower() in _HOSTS_SOMENTE_LOCAL


def _registrar_chamada[**P, R](
    ferramenta: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Uma linha de log `mcp_b2b_ferramenta` por chamada: parceiro que
    chamou (da chave), ferramenta e resultado (`ok`/`erro`). Só log, não a
    auditoria persistida (fora do MVP, `docs/ARCHITECTURE.md` §6).
    `functools.wraps` preserva a assinatura, de onde o SDK gera o schema
    de entrada da ferramenta."""

    @functools.wraps(ferramenta)
    async def envolvida(*args: P.args, **kwargs: P.kwargs) -> R:
        registro = {"event": "mcp_b2b_ferramenta", "parceiro": parceiro_atual()}
        registro["ferramenta"] = ferramenta.__name__
        try:
            resultado = await ferramenta(*args, **kwargs)
        except Exception as exc:
            logger.warning(
                "mcp_b2b_ferramenta",
                extra={"router": {**registro, "resultado": "erro", "erro": str(exc)}},
            )
            raise
        logger.info("mcp_b2b_ferramenta", extra={"router": {**registro, "resultado": "ok"}})
        return resultado

    return envolvida


def _parse_produto_id(produto_id: str) -> int:
    try:
        return int(produto_id)
    except ValueError as exc:
        raise ResourceError(f"produto_id inválido (esperado inteiro): {produto_id!r}") from exc


def create_b2b_mcp_server(
    session_factory: async_sessionmaker[AsyncSession],
    qdrant: QdrantRAGClient,
    embedders: EmbedderRegistry,
    token_verifier: TokenVerifier | None = None,
    auth: AuthSettings | None = None,
) -> MCPServer:
    """Monta o servidor MCP B2B com os 4 recursos de leitura e as 4
    ferramentas transacionais, recebendo as dependências já prontas (mesmo
    estilo de injeção por closure usado pelas dependências do FastAPI em
    `app.api.rag_dependencies`) — facilita testar o servidor de verdade
    (`server.read_resource(...)`/`server.call_tool(...)`) sem subir HTTP nem
    depender de `app.state`.

    `token_verifier`/`auth` ligam a autenticação por chave de parceiro
    (`app.mcp_server.auth`) no transporte HTTP. Ficam `None` nos testes que
    chamam o servidor direto, sem HTTP; `scripts/run_mcp_b2b_server.py`
    sempre passa os dois e não sobe sem chave.
    """

    server = MCPServer(
        name="mcp-b2b",
        title="MCP B2B — Catálogo, Estoque, Preços, Manuais e Ferramentas Transacionais",
        instructions=(
            "Servidor MCP B2B da empresa (protótipo de TCC) para "
            "revendedores/parceiros habilitados, autenticados por chave "
            "(Authorization: Bearer <chave>). Expõe catálogo de produtos, "
            "estoque por centro de distribuição, tabela de preços "
            "(promoção + descontos por volume) e busca semântica em "
            "manuais/documentação técnica (resources); validação de "
            "compatibilidade entre produtos, consulta de frete/prazo "
            "estimados, cotação automática com desconto por volume e "
            "reserva/pedido de estoque (tools)."
        ),
        token_verifier=token_verifier,
        auth=auth,
    )

    @server.resource(
        "catalogo://produtos{?categoria}",
        name="catalogo_produtos",
        description="Lista o catálogo de produtos, opcionalmente filtrado por categoria.",
        mime_type="application/json",
    )
    async def catalogo_produtos(categoria: str | None = None) -> str:
        try:
            async with session_factory() as session:
                produtos = await listar_produtos(session, categoria=categoria)
        except SQLAlchemyError as exc:
            raise ResourceError(f"Falha ao consultar o catálogo: {exc}") from exc
        itens = [CatalogoProdutoOut.model_validate(produto) for produto in produtos]
        return json.dumps([item.model_dump(mode="json") for item in itens], ensure_ascii=False)

    @server.resource(
        "catalogo://produtos/{produto_id}",
        name="catalogo_produto_detalhe",
        description="Detalhe de um produto do catálogo (sem preço/estoque, ver recursos próprios).",
        mime_type="application/json",
    )
    async def catalogo_produto_detalhe(produto_id: str) -> str:
        pid = _parse_produto_id(produto_id)
        try:
            async with session_factory() as session:
                produto = await obter_produto(session, pid)
        except SQLAlchemyError as exc:
            raise ResourceError(f"Falha ao consultar o catálogo: {exc}") from exc
        if produto is None:
            raise ResourceNotFoundError(f"Produto {pid} não encontrado no catálogo.")
        item = CatalogoProdutoOut.model_validate(produto)
        return item.model_dump_json()

    @server.resource(
        "estoque://produtos/{produto_id}",
        name="estoque_produto",
        description="Estoque de um produto por centro de distribuição.",
        mime_type="application/json",
    )
    async def estoque_produto(produto_id: str) -> str:
        # Achado no code-review (2026-09-24): o ResourceNotFoundError era
        # levantado DENTRO do try/except SQLAlchemyError aqui, diferente de
        # catalogo_produto_detalhe/precos_produto (levantado DEPOIS) — sem
        # bug funcional (ResourceNotFoundError não é SQLAlchemyError, nunca
        # seria capturado por engano), mas inconsistente. Alinhado ao mesmo
        # formato dos outros dois recursos.
        pid = _parse_produto_id(produto_id)
        try:
            async with session_factory() as session:
                produto = await obter_produto(session, pid)
                centros = await listar_estoque(session, pid) if produto is not None else []
        except SQLAlchemyError as exc:
            raise ResourceError(f"Falha ao consultar o estoque: {exc}") from exc
        if produto is None:
            raise ResourceNotFoundError(f"Produto {pid} não encontrado no catálogo.")
        saida = EstoqueProdutoOut(
            produto_id=pid,
            centros=[EstoqueCentroOut.model_validate(centro) for centro in centros],
        )
        return saida.model_dump_json()

    @server.resource(
        "precos://produtos/{produto_id}",
        name="precos_produto",
        description="Preço, promoção vigente e descontos por volume de um produto.",
        mime_type="application/json",
    )
    async def precos_produto(produto_id: str) -> str:
        pid = _parse_produto_id(produto_id)
        try:
            async with session_factory() as session:
                produto = await obter_produto(session, pid)
        except SQLAlchemyError as exc:
            raise ResourceError(f"Falha ao consultar a tabela de preços: {exc}") from exc
        if produto is None:
            raise ResourceNotFoundError(f"Produto {pid} não encontrado no catálogo.")
        saida = PrecoProdutoOut(
            produto_id=pid,
            preco=produto.preco,
            preco_promocional=produto.preco_promocional,
            promocao_valida_ate=produto.promocao_valida_ate,
            descontos_volume=[
                DescontoVolumeOut.model_validate(desconto) for desconto in produto.descontos_volume
            ],
        )
        return saida.model_dump_json()

    @server.resource(
        "manuais://busca/{domain}{?query}",
        name="manuais_busca",
        description=(
            "Busca semântica em manuais/documentação técnica restrita ao canal "
            "MCP B2B (collections com purpose=mcp_b2b — nunca o RAG do chat "
            "público). `domain` é um dos domínios de atendimento "
            "(vendas/suporte/atendimento); `query` é o texto de busca."
        ),
        mime_type="application/json",
    )
    async def manuais_busca(domain: str, query: str = "") -> str:
        if not query.strip():
            raise ResourceError("Parâmetro 'query' é obrigatório para a busca em manuais.")
        try:
            async with session_factory() as session:
                collections = await list_collections(session)
        except SQLAlchemyError as exc:
            raise ResourceError(f"Falha ao consultar as collections do RAG: {exc}") from exc

        # O parceiro B2B enxerga o RAG principal (a collection `chat` ativa
        # — mesmo conteúdo do chat público) MAIS o conteúdo exclusivo do
        # canal B2B (`purpose="mcp_b2b"`); só o caminho inverso é vedado (o
        # chat público nunca busca `purpose="mcp_b2b"`, garantido em
        # `ActiveCollectionRagClient.search`) — ver decisão de 2026-09-30 em
        # docs/ARCHITECTURE.md §6. Filtrado aqui em vez de uma função
        # dedicada em `collections_registry`: é o único consumidor desse
        # recorte até agora (regra 8, CLAUDE.md).
        b2b_collections = [
            c
            for c in collections
            if (c.purpose == "mcp_b2b" and c.is_active) or (c.purpose == "chat" and c.is_active)
        ]

        # Busca em paralelo (achado no code-review de 2026-09-24: um
        # round-trip por collection, não N sequenciais) e agrega por score —
        # lógica compartilhada com o modo admin do chat (decisão de
        # 2026-09-30, docs/ARCHITECTURE.md §6), extraída para
        # `app.rag.multi_collection_search`.
        pares = await buscar_em_varias_collections(
            b2b_collections, qdrant, embedders, query, domain, top_k=DEFAULT_MANUAIS_TOP_K
        )
        resultados = [
            ManualResultadoOut(
                content=documento.content,
                source=documento.source,
                score=documento.score,
                collection=collection.name,
            )
            for collection, documento in pares
        ]

        saida = ManualBuscaOut(resultados=resultados)
        return saida.model_dump_json()

    @asynccontextmanager
    async def _abrir_sessao_bd(mensagem_erro: str):
        """Context manager utilitário para abrir sessão no BD e traduzir exceções
        incomuns de SQLAlchemy em ToolError com mensagem contextual."""
        try:
            async with session_factory() as session:
                yield session
        except SQLAlchemyError as exc:
            raise ToolError(f"{mensagem_erro}: {exc}") from exc

    async def _obter_e_validar_produtos(
        session: AsyncSession, itens: list[ItemQuantidadeIn]
    ) -> dict[int, Produto]:
        """Helper para carregar em lote e validar a existência de todos os produtos
        solicitados numa lista de itens."""
        produto_ids = [item.produto_id for item in itens]
        produtos = await obter_produtos_por_ids(session, produto_ids)
        for item in itens:
            if item.produto_id not in produtos:
                raise ToolError(f"Produto {item.produto_id} não encontrado no catálogo.")
        return produtos

    # --- Ferramenta 1: validação de compatibilidade --------------------------

    @server.tool(
        name="validar_compatibilidade",
        description=(
            "Valida se dois produtos do catálogo são compatíveis entre si "
            "(ex.: peça/acessório e equipamento principal). A relação é "
            "simétrica: não importa qual dos dois é o 'principal'."
        ),
    )
    @_registrar_chamada
    async def validar_compatibilidade(
        produto_id: int, produto_relacionado_id: int
    ) -> CompatibilidadeOut:
        async with _abrir_sessao_bd("Falha ao consultar a compatibilidade"):
            async with session_factory() as session:
                await _obter_e_validar_produtos(
                    session,
                    [
                        ItemQuantidadeIn(produto_id=produto_id, quantidade=1),
                        ItemQuantidadeIn(produto_id=produto_relacionado_id, quantidade=1),
                    ],
                )
                compativel = await sao_compativeis(session, produto_id, produto_relacionado_id)
        return CompatibilidadeOut(
            produto_id=produto_id,
            produto_relacionado_id=produto_relacionado_id,
            compativel=compativel,
        )

    # --- Ferramenta 2: consulta de frete e prazos -----------------------------

    @server.tool(
        name="consultar_frete",
        description=(
            "Estima custo e prazo de frete para um CEP a partir do peso total "
            "dos itens informados. Estimativa interna determinística — não "
            "consulta nenhuma transportadora/Correios real."
        ),
    )
    @_registrar_chamada
    async def consultar_frete(cep: str, itens: list[FreteItemIn]) -> FreteOut:
        cep_digitos = "".join(ch for ch in cep if ch.isdigit())
        if len(cep_digitos) != 8:
            raise ToolError(f"CEP inválido (esperado 8 dígitos): {cep!r}")
        regiao = cep_digitos[0]
        custo_base, prazo_dias = _FRETE_CUSTO_BASE_E_PRAZO_POR_REGIAO[regiao]

        async with _abrir_sessao_bd("Falha ao consultar o catálogo para o frete"):
            async with session_factory() as session:
                produtos = await _obter_e_validar_produtos(session, itens)
                peso_total = Decimal("0")
                for item in itens:
                    produto = produtos[item.produto_id]
                    # MVP: produto sem peso_kg cadastrado entra como peso zero
                    # na estimativa (não bloqueia a cotação de frete) — ver
                    # docs/ARCHITECTURE.md §5, decisão de 2026-09-24.
                    peso_unitario = produto.peso_kg or Decimal("0")
                    peso_total += peso_unitario * item.quantidade

        # Arredondado a centavos (2 casas) — mesmo motivo do arredondamento
        # em `calcular_item_cotacao` (ver docstring lá): a multiplicação por
        # `_FRETE_ADICIONAL_POR_KG` produz mais casas decimais que
        # `Numeric(10, 2)` comporta.
        custo_estimado = (custo_base + _FRETE_ADICIONAL_POR_KG * peso_total).quantize(
            Decimal("0.01")
        )
        return FreteOut(
            cep=cep_digitos,
            peso_total_kg=peso_total,
            custo_estimado=custo_estimado,
            prazo_dias=prazo_dias,
        )

    # --- Ferramenta 3: cotação automática --------------------------------------

    @server.tool(
        name="cotar",
        description=(
            "Gera uma cotação automática para uma lista de itens (produto + "
            "quantidade), aplicando preço promocional vigente e a maior faixa "
            "de desconto por volume atingida por cada item."
        ),
    )
    @_registrar_chamada
    async def cotar(itens: list[CotacaoItemIn]) -> CotacaoOut:
        agora = datetime.now(UTC)
        async with _abrir_sessao_bd("Falha ao consultar o catálogo para a cotação"):
            async with session_factory() as session:
                produtos = await _obter_e_validar_produtos(session, itens)
                itens_saida: list[CotacaoItemOut] = []
                for item in itens:
                    produto = produtos[item.produto_id]
                    preco_unitario, percentual, subtotal = calcular_item_cotacao(
                        produto, item.quantidade, agora
                    )
                    itens_saida.append(
                        CotacaoItemOut(
                            produto_id=item.produto_id,
                            quantidade=item.quantidade,
                            preco_unitario=preco_unitario,
                            percentual_desconto_aplicado=percentual,
                            subtotal=subtotal,
                        )
                    )

        total = sum((item.subtotal for item in itens_saida), Decimal("0"))
        return CotacaoOut(itens=itens_saida, total=total)

    # --- Ferramenta 4: reserva/pedido -------------------------------------------

    @server.tool(
        name="reservar_pedido",
        description=(
            "Cria uma reserva/pedido para uma lista de itens (produto, "
            "quantidade e centro de distribuição), decrementando o estoque "
            "correspondente. Falha sem gravar nada se qualquer item não tiver "
            "estoque suficiente."
        ),
    )
    @_registrar_chamada
    async def reservar_pedido(itens: list[PedidoItemIn]) -> PedidoOut:
        itens_tuplas = [
            (item.produto_id, item.quantidade, item.centro_distribuicao) for item in itens
        ]
        try:
            async with _abrir_sessao_bd("Falha ao gravar a reserva/pedido"):
                async with session_factory() as session:
                    pedido = await criar_pedido(session, itens_tuplas)
        except ProdutoInexistenteError as exc:
            raise ToolError(str(exc)) from exc
        except EstoqueInsuficienteError as exc:
            raise ToolError(str(exc)) from exc
        return PedidoOut.model_validate(pedido)

    return server
