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

import json
import re
from decimal import Decimal

from pydantic import BaseModel, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.catalog import calcular_item_cotacao, listar_estoque, obter_produto, sao_compativeis
from app.db.models import Produto
from app.router.classifier import normalize, strip_code_fence
from app.router.llm_client import LLMClient


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
    quantidade: int | None = None
    produto_relacionado_nome: str | None = None
    compativel: bool | None = None


# MVP: tokenização simples da mensagem do cliente (etapa 1, spec §2) para
# reduzir o catálogo (potencialmente ~1000 produtos) a um punhado de
# candidatos plausíveis, antes de qualquer chamada LLM — heurística de MVP,
# não NLP de verdade. Reaproveita `app.router.classifier.normalize`
# (minúsculas, sem acentos) em vez de uma terceira implementação de
# normalização de texto no projeto.
# Lista compacta de propósito: sem o `fmt: off`, o formatador poria uma
# palavra por linha.
# fmt: off
_STOPWORDS = frozenset(
    {
        "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
        "para", "por", "com", "uma", "um", "uns", "umas", "que", "tem",
        "voces", "voce", "preciso", "queria", "quero", "gostaria", "ola",
        "favor", "obrigado", "obrigada", "bom", "boa", "dia", "tarde",
        "noite", "quanto", "custa", "custam", "sobre", "tenho", "onde",
        "quando", "como", "tudo", "bem", "cotacao", "estoque", "preco",
        "disponivel",
    }
)
# fmt: on

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Etapa 1 (spec §8): teto de candidatos devolvidos por `buscar_candidatos`
# antes da desambiguação por LLM (etapa 2) — nome explícito no módulo por
# ser o mesmo valor citado na spec, não um "10" mágico solto na assinatura.
SALES_CANDIDATOS_LIMITE = 10


def extrair_termos_busca(message: str) -> list[str]:
    """Extrai palavras significativas da mensagem (minúsculas, sem acentos,
    sem pontuação) para a busca de candidatos — descarta palavras com 2
    caracteres ou menos e a stopword list acima.

    # MVP: exceção à regra de tamanho — qualquer token com dígito (ex.: "15"
    # em "GD-15") é mantido mesmo com 2 caracteres ou menos, porque dígito é
    # justamente o que torna um token parecido com código de produto (SKU) e
    # vale a pena preservar para a busca, ao contrário de uma palavra curta
    # qualquer sem dígito.
    """
    termos_normalizados = _TOKEN_RE.findall(normalize(message))
    return [
        termo
        for termo in termos_normalizados
        if (len(termo) > 2 or any(c.isdigit() for c in termo)) and termo not in _STOPWORDS
    ]


# MVP: chama `app.db.catalog` diretamente, no mesmo processo — não abre uma
# conexão MCP real contra o `mcp-b2b-server` separado (spec §4).
class SalesCatalogClient:
    """Injetado em `handle_message` (mesmo padrão opcional de
    `calendar_client`/`scheduling_config`) — construído uma vez em
    `app.main` a partir do `db_sessionmaker` já existente, igual a
    `create_b2b_mcp_server(session_factory, ...)`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def buscar_candidatos(
        self, termos: list[str], limite: int = SALES_CANDIDATOS_LIMITE
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
            # MVP: quantidade do LLM usada sem faixa de sanidade (valor
            # não-numérico já é descartado inteiro em extract_sales_slots,
            # via ValidationError, antes de chegar aqui; valores <=0 ou muito
            # grandes não são validados).
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
                quantidade=quantidade,
                produto_relacionado_nome=produto_relacionado_nome,
                compativel=compativel,
            )


_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando um cliente numa conversa de vendas. A partir da lista de \
produtos candidatos abaixo (já filtrada do catálogo da empresa), identifique \
qual produto o cliente está perguntando, se houver um segundo produto \
mencionado para checar compatibilidade, e a quantidade desejada.

Produtos candidatos (escolha o ID de um deles, ou null se nenhum corresponder \
ao que o cliente pediu):
{candidatos}

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"produto_id": <id ou null>, \
"produto_relacionado_id": <id ou null>, "quantidade": <número ou null>}}. \
"produto_id" e "produto_relacionado_id" DEVEM ser um dos IDs listados acima \
(nunca invente um ID que não está na lista); use null se o cliente não \
mencionar um segundo produto para checar compatibilidade, ou nenhum produto \
da lista corresponder ao pedido."""


def _formatar_candidatos(candidatos: list[CandidatoProduto]) -> str:
    return "\n".join(
        f"- id={candidato.id}: {candidato.nome} (categoria: {candidato.categoria})"
        for candidato in candidatos
    )


def _parse_extraction(raw_text: str) -> VendaSlots:
    parsed = json.loads(strip_code_fence(raw_text))
    return VendaSlots(**parsed)


async def extract_sales_slots(
    message: str,
    recent_messages: list[str],
    candidatos: list[CandidatoProduto],
    llm_client: LLMClient,
) -> VendaSlots:
    """Uma chamada LLM: recebe a mensagem do cliente junto com a lista de
    candidatos já filtrada (etapa 1, `SalesCatalogClient.buscar_candidatos`)
    e escolhe o `produto_id` certo entre eles — copiar um ID de uma lista
    real e pequena é uma tarefa muito mais confiável para o LLM do que
    inventar um nome livre que depois precisa ser casado (spec §2). Mesmo
    padrão de `app.router.scheduling.extract_booking_slots`: prompt → JSON →
    parse com `ValidationError`/`JSONDecodeError` tratado, fallback pra
    `VendaSlots()` vazio em qualquer falha de parsing (não quebra o turno)."""
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        candidatos=_formatar_candidatos(candidatos),
        contexto=contexto,
        mensagem=message,
    )
    response = await llm_client.generate(prompt)
    try:
        slots = _parse_extraction(response.text)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return VendaSlots()

    ids_validos = {candidato.id for candidato in candidatos}
    if slots.produto_id is not None and slots.produto_id not in ids_validos:
        slots.produto_id = None
    if slots.produto_relacionado_id is not None and slots.produto_relacionado_id not in ids_validos:
        slots.produto_relacionado_id = None
    return slots
