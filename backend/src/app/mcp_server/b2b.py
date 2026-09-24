"""Servidor MCP B2B provido pela empresa (R12, Fase 5) — expõe os 4 recursos
de leitura descritos em `docs/ARCHITECTURE.md` §6: catálogo, estoque, tabela
de preços e manuais/documentação.

Reaproveita o "backend único de dados" já modelado no item anterior desta
fase (`app.db.catalog`, sobre `Produto`/`ProdutoEstoque`/
`ProdutoDescontoVolume`) para os três recursos estruturados, e a
infraestrutura RAG já existente (`app.rag.qdrant_client`) para o quarto
recurso — buscando especificamente nas collections com
`purpose="mcp_b2b"` (nunca a collection ativa do chat público, ver decisão
de 2026-09-21 em `docs/ARCHITECTURE.md` §5).

# MVP: servidor de uso interno, sem autenticação por parceiro nem exposição
pública (ver `docs/ARCHITECTURE.md` §5/§6 e `docs/ROADMAP.md`, Fase 5) — o
mesmo nível de confiança de rede local já aceito para Qdrant/Postgres/
`calendar-mcp-server` neste protótipo. Só os 4 recursos de LEITURA — as 4
ferramentas transacionais (compatibilidade, frete, cotação, reserva/pedido)
são o próximo item desta mesma fase, ainda não implementadas aqui.

Modelado como *MCP resources* (não *tools*): os quatro itens deste item são
dados somente-leitura, endereçáveis por URI (`catalogo://`, `estoque://`,
`precos://`, `manuais://`) — o protocolo MCP reserva "tools" para
ações/automações, que é exatamente a categoria das 4 ferramentas
transacionais do próximo item (ver "Recursos" vs "Ferramentas" em
`docs/ARCHITECTURE.md` §6).

SDK: `mcp` (Python SDK oficial), interface `mcp.server.mcpserver.MCPServer`
— nesta versão instalada do pacote (2.x), a antiga `FastMCP` foi renomeada
para `MCPServer` (ver `pyproject.toml`, `mcp>=2.0`).
"""

from __future__ import annotations

import asyncio
import json
import logging

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceError, ResourceNotFoundError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.catalog import listar_estoque, listar_produtos, obter_produto
from app.models.mcp_b2b import (
    CatalogoProdutoOut,
    DescontoVolumeOut,
    EstoqueCentroOut,
    EstoqueProdutoOut,
    ManualBuscaOut,
    ManualResultadoOut,
    PrecoProdutoOut,
)
from app.rag.collections_registry import list_collections
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

# MVP: pool de resultados por collection mcp_b2b consultada, sem reranking
# entre collections além da ordenação por score — suficiente para a base
# pequena deste protótipo (ver docs/ARCHITECTURE.md §6, "Escopo no
# protótipo").
DEFAULT_MANUAIS_TOP_K = 5


def _parse_produto_id(produto_id: str) -> int:
    try:
        return int(produto_id)
    except ValueError as exc:
        raise ResourceError(f"produto_id inválido (esperado inteiro): {produto_id!r}") from exc


def create_b2b_mcp_server(
    session_factory: async_sessionmaker[AsyncSession],
    qdrant: QdrantRAGClient,
    embedders: EmbedderRegistry,
) -> MCPServer:
    """Monta o servidor MCP B2B com os 4 recursos de leitura, recebendo as
    dependências já prontas (mesmo estilo de injeção por closure usado pelas
    dependências do FastAPI em `app.api.rag_dependencies`) — facilita testar
    o servidor de verdade (`server.read_resource(...)`) sem subir HTTP nem
    depender de `app.state`.
    """

    server = MCPServer(
        name="mcp-b2b",
        title="MCP B2B — Catálogo, Estoque, Preços e Manuais",
        instructions=(
            "Servidor MCP interno da empresa (uso interno/prototípo de TCC, "
            "sem autenticação por parceiro). Expõe catálogo de produtos, "
            "estoque por centro de distribuição, tabela de preços "
            "(promoção + descontos por volume) e busca semântica em "
            "manuais/documentação técnica."
        ),
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

        # Só collections restritas ao canal MCP B2B (purpose="mcp_b2b") —
        # nunca as de purpose="chat", que são as elegíveis ao chat público
        # (ver decisão de 2026-09-21 em docs/ARCHITECTURE.md §5). Filtrado
        # aqui em vez de uma função dedicada em `collections_registry`: é o
        # único consumidor desse recorte até agora (regra 8, CLAUDE.md).
        mcp_b2b_collections = [c for c in collections if c.purpose == "mcp_b2b"]

        # Achado no code-review (2026-09-24): buscar uma collection de cada
        # vez fazia o tempo total crescer O(N) round-trips ao Qdrant, com N
        # = nº de collections mcp_b2b — as buscas são independentes, então
        # rodam em paralelo (asyncio.gather), custando só o round-trip mais
        # lento em vez da soma de todos.
        async def _buscar(collection):
            embedder = embedders.get(collection.embedding_model)
            return await qdrant.search(collection.name, embedder, query, domain)

        buscas = await asyncio.gather(
            *(_buscar(collection) for collection in mcp_b2b_collections),
            return_exceptions=True,
        )

        resultados: list[ManualResultadoOut] = []
        for collection, busca in zip(mcp_b2b_collections, buscas, strict=True):
            if isinstance(busca, RAGConnectionError):
                logger.warning(
                    "mcp_b2b_manuais_busca_falhou collection=%s domain=%s erro=%s",
                    collection.name,
                    domain,
                    busca,
                )
                continue
            if isinstance(busca, BaseException):
                raise busca
            resultados.extend(
                ManualResultadoOut(
                    content=documento.content,
                    source=documento.source,
                    score=documento.score,
                    collection=collection.name,
                )
                for documento in busca
            )

        resultados.sort(key=lambda r: r.score, reverse=True)
        saida = ManualBuscaOut(resultados=resultados[:DEFAULT_MANUAIS_TOP_K])
        return saida.model_dump_json()

    return server
