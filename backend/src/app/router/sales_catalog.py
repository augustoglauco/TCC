"""Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5) — ver
docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.

Resolve produto/quantidade/compatibilidade mencionados numa mensagem de
Vendas em duas etapas: busca de candidatos por SQL (`buscar_candidatos`,
este módulo, sem LLM) e desambiguação por LLM entre os candidatos
(`extract_sales_slots`, mesmo módulo) — necessário porque o catálogo real
vai crescer para ~1000 produtos, onde casar nome por substring direto é
ambíguo demais (spec §2). `SalesCatalogClient` chama `app.db.catalog`
diretamente (mesmo processo) — não é um cliente MCP de verdade contra o
processo `mcp-b2b-server` separado (spec §4).

Mesmo padrão de módulo de `app.router.scheduling`: lógica de domínio pura
(sem tipos de streaming SSE), consumida por `app.router.orchestrator`.
"""

import re
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.catalog import calcular_item_cotacao, listar_estoque, obter_produto, sao_compativeis
from app.db.models import Produto
from app.router.classifier import normalize


class CandidatoProduto(BaseModel):
    id: int
    nome: str
    categoria: str


class VendaSlots(BaseModel):
    produto_id: int | None = None
    produto_relacionado_id: int | None = None
    quantidade: int | None = None


class DadosCatalogoVendas(BaseModel):
    produto_nome: str
    estoque_total: int
    cotacao: tuple[Decimal, Decimal, Decimal] | None = None
    produto_relacionado_nome: str | None = None
    compativel: bool | None = None


# Etapa 1 (spec §2): tokenização simples da mensagem do cliente para reduzir
# o catálogo (potencialmente ~1000 produtos) a um punhado de candidatos
# plausíveis, antes de qualquer chamada LLM. Heurística de MVP, não NLP de
# verdade — reaproveita `app.router.classifier.normalize` (minúsculas, sem
# acentos) em vez de uma terceira implementação de normalização de texto no
# projeto.
_STOPWORDS = frozenset(
    {
        "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
        "para", "por", "com", "uma", "um", "uns", "umas", "que", "tem",
        "voces", "voce", "preciso", "queria", "quero", "gostaria", "ola",
        "favor", "obrigado", "obrigada", "bom", "boa", "dia", "tarde",
        "noite", "quanto", "custa", "custam", "sobre", "tenho", "onde",
        "quando", "como", "tudo", "bem",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def extrair_termos_busca(message: str) -> list[str]:
    """Extrai palavras significativas da mensagem (minúsculas, sem acentos,
    sem pontuação) para a busca de candidatos — descarta palavras com 2
    caracteres ou menos e a stopword list acima."""
    termos_normalizados = _TOKEN_RE.findall(normalize(message))
    return [termo for termo in termos_normalizados if len(termo) > 2 and termo not in _STOPWORDS]


class SalesCatalogClient:
    """Injetado em `handle_message` (mesmo padrão opcional de
    `calendar_client`/`scheduling_config`) — construído uma vez em
    `app.main` a partir do `db_sessionmaker` já existente, igual a
    `create_b2b_mcp_server(session_factory, ...)`. Chama `app.db.catalog`
    diretamente, no mesmo processo (spec §4) — não abre conexão MCP real."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def buscar_candidatos(
        self, termos: list[str], limite: int = 10
    ) -> list[CandidatoProduto]:
        """`OR` de `ILIKE '%termo%'` contra `Produto.nome`/`Produto.categoria`
        por termo, `LIMIT limite`. Sem ranking por relevância — a
        desambiguação de verdade é a etapa 2 (LLM, `extract_sales_slots`),
        que só recebe esta lista já reduzida."""
        if not termos:
            return []
        condicoes = [
            condicao
            for termo in termos
            for condicao in (
                Produto.nome.ilike(f"%{termo}%"),
                Produto.categoria.ilike(f"%{termo}%"),
            )
        ]
        async with self._session_factory() as session:
            result = await session.execute(
                select(Produto.id, Produto.nome, Produto.categoria)
                .where(or_(*condicoes))
                .order_by(Produto.id)
                .limit(limite)
            )
            return [
                CandidatoProduto(id=linha.id, nome=linha.nome, categoria=linha.categoria)
                for linha in result.all()
            ]

    async def consultar_detalhes(
        self, produto_id: int, produto_relacionado_id: int | None, quantidade: int | None
    ) -> DadosCatalogoVendas | None:
        """Agrega estoque (soma entre centros de distribuição — o resumo do
        chat não precisa do detalhe por CD, já disponível via o resource MCP
        `estoque://` para quem precisar), cotação (só se `quantidade` veio)
        e compatibilidade (só se `produto_relacionado_id` veio e existir).
        Devolve `None` se `produto_id` não existir."""
        async with self._session_factory() as session:
            produto = await obter_produto(session, produto_id)
            if produto is None:
                return None
            estoques = await listar_estoque(session, produto_id)
            estoque_total = sum(estoque.quantidade for estoque in estoques)
            cotacao = None
            if quantidade is not None and quantidade > 0:
                cotacao = calcular_item_cotacao(produto, quantidade)
            produto_relacionado_nome = None
            compativel = None
            if produto_relacionado_id is not None:
                relacionado = await obter_produto(session, produto_relacionado_id)
                if relacionado is not None:
                    produto_relacionado_nome = relacionado.nome
                    compativel = await sao_compativeis(session, produto_id, produto_relacionado_id)
            return DadosCatalogoVendas(
                produto_nome=produto.nome,
                estoque_total=estoque_total,
                cotacao=cotacao,
                produto_relacionado_nome=produto_relacionado_nome,
                compativel=compativel,
            )
