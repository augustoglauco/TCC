# Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar o quarto item da Fase 5 (R12) — quando o domínio de uma mensagem é `vendas` e o cliente menciona um produto do catálogo, a resposta do assistente passa a usar dados estruturados reais (estoque, cotação com desconto por volume, compatibilidade) em vez de depender só do RAG textual genérico.

**Architecture:** Um novo módulo `app.router.sales_catalog` resolve produto/quantidade da mensagem em duas etapas (busca de candidatos por SQL `ILIKE`, depois desambiguação por uma chamada LLM entre os candidatos — necessário porque o catálogo vai crescer para ~1000 produtos, onde casar por substring direto é ambíguo demais) e agrega os dados do catálogo (`app.db.catalog`, chamado diretamente, sem MCP real). `orchestrator.handle_message` roda essa consulta em paralelo com a busca RAG já existente (`asyncio.TaskGroup`) quando o domínio é `vendas`, e injeta o resultado como um bloco extra no prompt do LLM.

**Tech Stack:** Python 3.13, SQLAlchemy 2.0 async, Pydantic v2, pytest + pytest-asyncio, mesmo padrão de extração estruturada via LLM já usado em `app.router.scheduling.extract_booking_slots`.

**Spec:** `docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md` — este plano segue a spec seção a seção; os executores devem ler as duas.

## Global Constraints

- Resolução de produto em duas etapas: busca de candidatos por SQL `ILIKE` (sem LLM, até 10 candidatos), depois uma única chamada LLM que escolhe entre os candidatos já filtrados (spec §2). Nunca casar nome livre por substring direto contra a tabela inteira.
- `SalesCatalogClient` chama `app.db.catalog` diretamente (mesmo processo) — nunca abre uma conexão MCP real contra `mcp-b2b-server` (spec §4).
- Capacidades automáticas nesta entrega: estoque, cotação, compatibilidade. `consultar_frete` e `reservar_pedido` ficam fora (spec §9) — não implementar.
- O bloco de dados do catálogo **complementa** o RAG no prompt, nunca substitui (spec §5, item 3; §9).
- Qualquer falha na consulta de vendas (erro de banco, resposta do LLM não-JSON) é capturada e loga — nunca derruba o turno nem propaga como exceção (spec §5, item 2; mesmo espírito de `analyze_tone`).
- `sales_catalog_client` é um parâmetro **opcional** de `handle_message` (`SalesCatalogClient | None = None`) — ausente, o comportamento de Vendas é idêntico ao atual (spec §5).
- Zero configuração nova em `.env.example` — limite de candidatos fica como constante no módulo (spec §8).
- `except* RAGConnectionError` dentro do novo `asyncio.TaskGroup` precisa re-levantar a exceção **original** (`raise eg.exceptions[0]`, nunca um `raise` nu) para não quebrar `test_orchestrator.py::test_rag_indisponivel_propaga_erro` (nome real a confirmar na Task 3), que espera `pytest.raises(RAGConnectionError)`.
- Desvio deliberado do nome usado na spec: a spec (§3) escreve `_extrair_termos_busca` (privada); este plano a torna **pública** (`extrair_termos_busca`, sem underscore) porque `orchestrator.py` precisa chamá-la fora do módulo — mesma convenção já usada no projeto (`app.router.classifier.normalize`/`strip_code_fence` são públicas pelo mesmo motivo; `app.router.scheduling._strip_code_fence` continua privada por só ser usada dentro do próprio módulo). Os demais nomes batem com a spec.

---

## File Structure

**Criar:**
- `backend/src/app/router/sales_catalog.py` — `CandidatoProduto`, `VendaSlots`, `DadosCatalogoVendas`, `extrair_termos_busca`, `SalesCatalogClient`, `extract_sales_slots`.
- `backend/tests/test_sales_catalog.py`

**Modificar:**
- `backend/src/app/router/orchestrator.py` — `_buscar_documentos_rag` (extração da lógica de busca RAG já existente para rodar como task), `_consultar_vendas` (nova), `_formatar_dados_catalogo_vendas` (nova), `_build_prompt` (novo parâmetro `dados_catalogo`), bloco RAG de `handle_message` reestruturado com `asyncio.TaskGroup`, novo parâmetro `sales_catalog_client` em `handle_message`.
- `backend/tests/test_orchestrator.py` — `_FakeSalesCatalogClient`, testes do novo fluxo.
- `backend/src/app/main.py` — instancia `SalesCatalogClient` em `app.state`.
- `backend/src/app/api/chat.py` — `get_sales_catalog_client`, novo parâmetro em `send_message`, passa pra `handle_message`.
- `backend/tests/test_chat_api.py` — override de `get_sales_catalog_client` em `_build_app` (mesmo padrão de `get_calendar_client`/`get_scheduling_config`).
- `docs/ROADMAP.md` — marca o item da Fase 5 como concluído.

---

## Task 1: `sales_catalog.py` — busca de candidatos e detalhes do catálogo (sem LLM)

**Files:**
- Create: `backend/src/app/router/sales_catalog.py`
- Test: `backend/tests/test_sales_catalog.py`

**Interfaces:**
- Consumes: `app.db.catalog.obter_produto(session, produto_id) -> Produto | None`; `app.db.catalog.listar_estoque(session, produto_id) -> list[ProdutoEstoque]` (cada item tem `.quantidade: int`); `app.db.catalog.calcular_item_cotacao(produto, quantidade, agora=None) -> tuple[Decimal, Decimal, Decimal]` (unitário, % desconto, subtotal); `app.db.catalog.sao_compativeis(session, produto_id, outro_produto_id) -> bool`; `app.db.models.Produto` (campos `id: int`, `nome: str`, `categoria: str`); `app.router.classifier.normalize(text: str) -> str` (minúsculas, sem acentos).
- Produces: `CandidatoProduto(BaseModel)` — `id: int`, `nome: str`, `categoria: str`. `DadosCatalogoVendas(BaseModel)` — `produto_nome: str`, `estoque_total: int`, `cotacao: tuple[Decimal, Decimal, Decimal] | None`, `produto_relacionado_nome: str | None`, `compativel: bool | None`. `extrair_termos_busca(message: str) -> list[str]`. `SalesCatalogClient(session_factory: async_sessionmaker[AsyncSession])` com `async def buscar_candidatos(self, termos: list[str], limite: int = 10) -> list[CandidatoProduto]` e `async def consultar_detalhes(self, produto_id: int, produto_relacionado_id: int | None, quantidade: int | None) -> DadosCatalogoVendas | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_sales_catalog.py
"""Testes de app.router.sales_catalog (R12, Fase 5 — orquestrador como
integrador do MCP B2B em Vendas). Ver
docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.
"""

from decimal import Decimal

import pytest

from app.db.catalog import (
    adicionar_desconto_volume,
    atualizar_estoque,
    criar_compatibilidade,
    criar_produto,
)
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.router.sales_catalog import SalesCatalogClient, extrair_termos_busca


async def _cria_produto(session, **overrides):
    defaults = dict(
        nome="Gerador Diesel GD-15",
        descricao="Potência de 15 kVA.",
        preco=Decimal("24900.00"),
        categoria="geradores",
    )
    defaults.update(overrides)
    return await criar_produto(session, **defaults)


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


def test_extrair_termos_busca_remove_stopwords_e_palavras_curtas():
    termos = extrair_termos_busca("Olá, eu queria saber se vocês têm um gerador de 15 kVA")

    assert "gerador" in termos
    assert "ola" not in termos
    assert "queria" not in termos
    assert "um" not in termos
    assert "de" not in termos


def test_extrair_termos_busca_normaliza_acentos():
    termos = extrair_termos_busca("Preciso de uma cabine de insonorização")

    assert "insonorizacao" in termos


def test_extrair_termos_busca_mensagem_sem_termos_significativos_devolve_lista_vazia():
    assert extrair_termos_busca("Oi, tudo bem?") == []


async def test_buscar_candidatos_encontra_por_nome(factory):
    async with factory() as session:
        await _cria_produto(session, nome="Gerador Diesel GD-15")
        await _cria_produto(session, nome="Cabine de Insonorização")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["gerador"])

    assert len(candidatos) == 1
    assert candidatos[0].nome == "Gerador Diesel GD-15"


async def test_buscar_candidatos_encontra_por_categoria(factory):
    async with factory() as session:
        await _cria_produto(session, nome="GD-15", categoria="geradores")
        await _cria_produto(session, nome="CI-30", categoria="cabines")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["geradores"])

    assert len(candidatos) == 1
    assert candidatos[0].nome == "GD-15"


async def test_buscar_candidatos_respeita_o_limite(factory):
    async with factory() as session:
        for i in range(15):
            await _cria_produto(session, nome=f"Gerador {i}")
    client = SalesCatalogClient(factory)

    candidatos = await client.buscar_candidatos(["gerador"], limite=10)

    assert len(candidatos) == 10


async def test_buscar_candidatos_sem_termos_devolve_lista_vazia(factory):
    client = SalesCatalogClient(factory)

    assert await client.buscar_candidatos([]) == []


async def test_buscar_candidatos_sem_match_devolve_lista_vazia(factory):
    async with factory() as session:
        await _cria_produto(session, nome="Gerador Diesel GD-15")
    client = SalesCatalogClient(factory)

    assert await client.buscar_candidatos(["parafuso"]) == []


async def test_consultar_detalhes_produto_inexistente_devolve_none(factory):
    client = SalesCatalogClient(factory)

    assert await client.consultar_detalhes(999, None, None) is None


async def test_consultar_detalhes_soma_estoque_entre_centros(factory):
    async with factory() as session:
        produto = await _cria_produto(session)
        await atualizar_estoque(session, produto.id, "CD-SP", 5)
        await atualizar_estoque(session, produto.id, "CD-RJ", 3)
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, None, None)

    assert dados.estoque_total == 8
    assert dados.cotacao is None
    assert dados.compativel is None


async def test_consultar_detalhes_com_quantidade_calcula_cotacao(factory):
    async with factory() as session:
        produto = await _cria_produto(session, preco=Decimal("100.00"))
        await adicionar_desconto_volume(session, produto.id, 10, Decimal("10.00"))
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, None, 10)

    assert dados.cotacao == (Decimal("100.00"), Decimal("10.00"), Decimal("900.00"))


async def test_consultar_detalhes_com_produto_relacionado_compativel(factory):
    async with factory() as session:
        produto = await _cria_produto(session, nome="QTA-100")
        relacionado = await _cria_produto(session, nome="GD-15")
        await criar_compatibilidade(session, produto.id, relacionado.id)
        produto_id, relacionado_id = produto.id, relacionado.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, relacionado_id, None)

    assert dados.produto_relacionado_nome == "GD-15"
    assert dados.compativel is True


async def test_consultar_detalhes_produto_relacionado_nao_compativel(factory):
    async with factory() as session:
        produto = await _cria_produto(session, nome="QTA-100")
        relacionado = await _cria_produto(session, nome="Cabine de Insonorização")
        produto_id, relacionado_id = produto.id, relacionado.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, relacionado_id, None)

    assert dados.compativel is False


async def test_consultar_detalhes_produto_relacionado_inexistente_ignora_compatibilidade(factory):
    async with factory() as session:
        produto = await _cria_produto(session)
        produto_id = produto.id
    client = SalesCatalogClient(factory)

    dados = await client.consultar_detalhes(produto_id, 999, None)

    assert dados.produto_relacionado_nome is None
    assert dados.compativel is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_sales_catalog.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.router.sales_catalog'`.

- [ ] **Step 3: Implement `sales_catalog.py`**

```python
# backend/src/app/router/sales_catalog.py
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

    async def buscar_candidatos(self, termos: list[str], limite: int = 10) -> list[CandidatoProduto]:
        """`OR` de `ILIKE '%termo%'` contra `Produto.nome`/`Produto.categoria`
        por termo, `LIMIT limite`. Sem ranking por relevância — a
        desambiguação de verdade é a etapa 2 (LLM, `extract_sales_slots`),
        que só recebe esta lista já reduzida."""
        if not termos:
            return []
        condicoes = [
            condicao
            for termo in termos
            for condicao in (Produto.nome.ilike(f"%{termo}%"), Produto.categoria.ilike(f"%{termo}%"))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_sales_catalog.py -v`
Expected: PASS (14 testes).

- [ ] **Step 5: Lint**

Run: `cd backend && uv run ruff check src/app/router/sales_catalog.py tests/test_sales_catalog.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd backend
git add src/app/router/sales_catalog.py tests/test_sales_catalog.py
git commit -m "feat(vendas): busca de candidatos e detalhes do catálogo por SQL (R12, Fase 5)"
```

---

## Task 2: `extract_sales_slots` — desambiguação de produto por LLM

**Files:**
- Modify: `backend/src/app/router/sales_catalog.py`
- Test: `backend/tests/test_sales_catalog.py`

**Interfaces:**
- Consumes: `CandidatoProduto`, `VendaSlots` (Task 1); `app.router.llm_client.LLMClient` (`async def generate(self, prompt: str) -> LLMResponse`, `LLMResponse.text: str`); `app.router.classifier.strip_code_fence(text: str) -> str`.
- Produces: `extract_sales_slots(message: str, recent_messages: list[str], candidatos: list[CandidatoProduto], llm_client: LLMClient) -> VendaSlots`.

- [ ] **Step 1: Write the failing tests**

Adicionar ao final de `backend/tests/test_sales_catalog.py`:

```python
from app.router.llm_client import LLMResponse
from app.router.sales_catalog import CandidatoProduto, VendaSlots, extract_sales_slots


class _FakeLLMClient:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=self._text, total_duration_ms=10.0)


async def test_extract_sales_slots_escolhe_o_produto_certo_entre_candidatos():
    candidatos = [
        CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores"),
        CandidatoProduto(id=2, nome="Cabine de Insonorização", categoria="cabines"),
    ]
    llm = _FakeLLMClient('{"produto_id": 1, "produto_relacionado_id": null, "quantidade": 3}')

    slots = await extract_sales_slots("Quero 3 geradores GD-15", [], candidatos, llm)

    assert slots.produto_id == 1
    assert slots.quantidade == 3
    assert "Gerador Diesel GD-15" in llm.last_prompt
    assert "Cabine de Insonorização" in llm.last_prompt


async def test_extract_sales_slots_extrai_produto_relacionado_para_compatibilidade():
    candidatos = [
        CandidatoProduto(id=1, nome="QTA-100", categoria="quadros"),
        CandidatoProduto(id=2, nome="Gerador Diesel GD-15", categoria="geradores"),
    ]
    llm = _FakeLLMClient('{"produto_id": 1, "produto_relacionado_id": 2, "quantidade": null}')

    slots = await extract_sales_slots("O QTA-100 funciona com o GD-15?", [], candidatos, llm)

    assert slots.produto_id == 1
    assert slots.produto_relacionado_id == 2


async def test_extract_sales_slots_sem_match_devolve_produto_id_none():
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient('{"produto_id": null, "produto_relacionado_id": null, "quantidade": null}')

    slots = await extract_sales_slots("Vocês vendem parafusos?", [], candidatos, llm)

    assert slots.produto_id is None


async def test_extract_sales_slots_resposta_nao_json_cai_em_fallback_vazio():
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient("desculpe, não entendi")

    slots = await extract_sales_slots("oi", [], candidatos, llm)

    assert slots == VendaSlots()


async def test_extract_sales_slots_ignora_id_inventado_fora_da_lista_de_candidatos():
    # Achado de robustez (mesmo espírito de scheduling.py): o LLM pode
    # "inventar" um ID que não está na lista de candidatos apesar da
    # instrução do prompt — valida contra os IDs reais antes de devolver.
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    llm = _FakeLLMClient('{"produto_id": 999, "produto_relacionado_id": null, "quantidade": null}')

    slots = await extract_sales_slots("Quero o produto X", [], candidatos, llm)

    assert slots.produto_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_sales_catalog.py -v -k extract_sales_slots`
Expected: FAIL com `ImportError: cannot import name 'extract_sales_slots'`.

- [ ] **Step 3: Implement `extract_sales_slots`**

Adicionar ao final de `backend/src/app/router/sales_catalog.py` (após `SalesCatalogClient`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_sales_catalog.py -v`
Expected: PASS (19 testes no total do arquivo).

- [ ] **Step 5: Lint**

Run: `cd backend && uv run ruff check src/app/router/sales_catalog.py tests/test_sales_catalog.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd backend
git add src/app/router/sales_catalog.py tests/test_sales_catalog.py
git commit -m "feat(vendas): desambiguação de produto por LLM entre candidatos (R12, Fase 5)"
```

---

## Task 3: Integração no `orchestrator.handle_message`

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `SalesCatalogClient`, `DadosCatalogoVendas`, `extrair_termos_busca`, `extract_sales_slots` (Tasks 1-2); `RAGConnectionError` (já importado em `orchestrator.py`).
- Produces: `handle_message(..., sales_catalog_client: SalesCatalogClient | None = None)`; `_build_prompt(message, documentos, domain, dados_catalogo=None)`.

Primeiro, leia o estado atual de `backend/src/app/router/orchestrator.py` nas faixas abaixo antes de editar (os números de linha podem ter mudado ligeiramente desde a escrita deste plano — use como referência, não como verdade absoluta; confirme lendo o arquivo):

- Imports do topo do arquivo (por volta da linha 1-35).
- `_build_prompt` (por volta da linha 57-83).
- O bloco RAG dentro de `handle_message`, do `if classification.domain == "fora_escopo":` até `prompt = _build_prompt(...)` (por volta da linha 571-624).
- A assinatura de `handle_message` (por volta da linha 370-382).

- [ ] **Step 1: Write the failing tests**

Adicionar a `backend/tests/test_orchestrator.py`. Primeiro, os imports novos no topo do arquivo (junto aos já existentes):

```python
from decimal import Decimal

from app.router.sales_catalog import CandidatoProduto, DadosCatalogoVendas
```

Depois, uma fake class ao lado de `_FakeCalendarClient` (mesmo padrão):

```python
class _FakeSalesCatalogClient:
    def __init__(
        self,
        candidatos: list[CandidatoProduto] | None = None,
        dados: DadosCatalogoVendas | None = None,
        buscar_exception: Exception | None = None,
    ) -> None:
        self._candidatos = candidatos if candidatos is not None else []
        self._dados = dados
        self._buscar_exception = buscar_exception
        self.termos_buscados: list[list[str]] = []
        self.detalhes_consultados: list[tuple[int, int | None, int | None]] = []

    async def buscar_candidatos(self, termos: list[str], limite: int = 10) -> list[CandidatoProduto]:
        self.termos_buscados.append(termos)
        if self._buscar_exception is not None:
            raise self._buscar_exception
        return self._candidatos

    async def consultar_detalhes(self, produto_id, produto_relacionado_id, quantidade):
        self.detalhes_consultados.append((produto_id, produto_relacionado_id, quantidade))
        return self._dados
```

E os testes em si (no final do arquivo):

```python
async def test_vendas_com_produto_identificado_injeta_dados_do_catalogo_no_prompt():
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"produto_id": 1, "produto_relacionado_id": null, "quantidade": 2}',
            total_duration_ms=10.0,
        )
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="manual", source="m.pdf", score=0.9)])
    candidatos = [CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    dados = DadosCatalogoVendas(
        produto_nome="Gerador Diesel GD-15",
        estoque_total=8,
        cotacao=(Decimal("24900.00"), Decimal("0"), Decimal("49800.00")),
        produto_relacionado_nome=None,
        compativel=None,
    )
    sales_catalog_client = _FakeSalesCatalogClient(candidatos=candidatos, dados=dados)

    await _coletar_eventos(
        "Quero cotação de 2 geradores GD-15",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
        sales_catalog_client=sales_catalog_client,
    )

    assert "Dados do catálogo interno" in local_client.last_prompt
    assert "Gerador Diesel GD-15" in local_client.last_prompt
    assert "8 unidade" in local_client.last_prompt


async def test_vendas_sem_sales_catalog_client_comportamento_identico_ao_atual():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="manual", source="m.pdf", score=0.9)])

    await _coletar_eventos(
        "Quero cotação de 2 geradores GD-15",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
    )

    assert "Dados do catálogo interno" not in local_client.last_prompt


async def test_vendas_sem_produto_reconhecivel_nao_chama_llm_de_extracao():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="manual", source="m.pdf", score=0.9)])
    sales_catalog_client = _FakeSalesCatalogClient(candidatos=[])

    await _coletar_eventos(
        "Quero cotação de um produto qualquer",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
        sales_catalog_client=sales_catalog_client,
    )

    # Só a chamada final de generate_stream — zero candidatos corta antes de
    # qualquer chamada LLM de desambiguação.
    assert local_client.calls == 1
    assert "Dados do catálogo interno" not in local_client.last_prompt


async def test_falha_no_sales_catalog_client_nao_derruba_a_resposta():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="manual", source="m.pdf", score=0.9)])
    sales_catalog_client = _FakeSalesCatalogClient(buscar_exception=RuntimeError("db indisponível"))

    eventos = await _coletar_eventos(
        "Quero cotação de 2 geradores GD-15",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
        sales_catalog_client=sales_catalog_client,
    )

    assert any(isinstance(evento, TokenEvent) for evento in eventos)
    assert "Dados do catálogo interno" not in local_client.last_prompt


async def test_dominio_suporte_nunca_chama_sales_catalog_client():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="manual", source="m.pdf", score=0.9)])
    sales_catalog_client = _FakeSalesCatalogClient(
        candidatos=[CandidatoProduto(id=1, nome="Gerador Diesel GD-15", categoria="geradores")]
    )

    await _coletar_eventos(
        "Meu produto não funciona, está com defeito",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        tone_monitor_enabled=False,
        sales_catalog_client=sales_catalog_client,
    )

    assert sales_catalog_client.termos_buscados == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && uv run pytest tests/test_orchestrator.py -v -k "vendas_com_produto or vendas_sem or falha_no_sales or dominio_suporte_nunca"`
Expected: FAIL — `TypeError: handle_message() got an unexpected keyword argument 'sales_catalog_client'`.

- [ ] **Step 3: Extrair a busca RAG existente para uma função nomeada**

Em `backend/src/app/router/orchestrator.py`, adicionar logo após `_build_prompt` (antes de `class RouterDecision`):

```python
async def _buscar_documentos_rag(
    message: str, recent_messages: list[str], domain: str, rag_client: RAGClient
) -> list[Document]:
    documentos = await rag_client.search(message, domain)
    if not documentos and recent_messages:
        # MVP: mensagem de acompanhamento sem match no RAG (ex.: "quais
        # outras opções?" logo após perguntar sobre câmeras) — tenta de
        # novo com o histórico recente concatenado à mensagem atual. Só
        # dispara quando a busca direta veio vazia, para não diluir o
        # embedding com contexto desnecessário no caso comum de pergunta
        # autocontida (ver docs/ARCHITECTURE.md §5).
        texto_busca = "\n".join([*recent_messages, message])
        documentos = await rag_client.search(texto_busca, domain)
    return documentos
```

Esta função só move o código que já existe dentro do bloco `else` de `handle_message` (busca + retry) — não muda nenhum comportamento sozinha; o passo 5 remove o código original do lugar antigo.

- [ ] **Step 4: Adicionar `_consultar_vendas` e `_formatar_dados_catalogo_vendas`**

Logo após `_buscar_documentos_rag`:

```python
async def _consultar_vendas(
    message: str,
    recent_messages: list[str],
    sales_catalog_client: SalesCatalogClient,
    local_client: LLMClient,
) -> DadosCatalogoVendas | None:
    """Busca de candidatos + desambiguação por LLM + detalhes do catálogo
    para uma mensagem de Vendas (spec
    docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md).
    Nunca levanta exceção — qualquer falha (erro de banco, resposta do LLM
    não-JSON já tratada dentro de `extract_sales_slots`) loga e devolve
    `None`, mesmo espírito de `analyze_tone` nunca derrubar o turno."""
    try:
        termos = extrair_termos_busca(message)
        if not termos:
            return None
        candidatos = await sales_catalog_client.buscar_candidatos(termos)
        if not candidatos:
            return None
        slots = await extract_sales_slots(message, recent_messages, candidatos, local_client)
        if slots.produto_id is None:
            return None
        return await sales_catalog_client.consultar_detalhes(
            slots.produto_id, slots.produto_relacionado_id, slots.quantidade
        )
    except Exception as exc:
        logger.warning(
            "vendas_catalogo_consulta_falhou",
            extra={"router": {"event": "vendas_catalogo_consulta_falhou", "erro": str(exc)}},
        )
        return None


def _formatar_dados_catalogo_vendas(dados: DadosCatalogoVendas) -> str:
    linhas = [f"Dados do catálogo interno (produto identificado: {dados.produto_nome}):"]
    linhas.append(f"- Estoque disponível: {dados.estoque_total} unidade(s)")
    if dados.cotacao is not None:
        preco_unitario, percentual, subtotal = dados.cotacao
        linhas.append(
            f"- Cotação: R$ {subtotal} "
            f"({percentual}% de desconto aplicado sobre R$ {preco_unitario}/unidade)"
        )
    if dados.compativel is not None:
        compat_texto = "sim" if dados.compativel else "não"
        linhas.append(f"- Compatível com {dados.produto_relacionado_nome}: {compat_texto}")
    return "\n".join(linhas)
```

- [ ] **Step 5: Atualizar `_build_prompt`**

Trocar a assinatura e o corpo de `_build_prompt` (mantém o resto igual):

```python
def _build_prompt(
    message: str,
    documentos: list[Document],
    domain: Domain,
    dados_catalogo: str | None = None,
) -> str:
    """Monta o prompt final: prompt de sistema do domínio (playbook) +
    dados do catálogo de Vendas (quando houver, R12 Fase 5) + contexto de
    RAG (quando houver) + mensagem do cliente.

    # MVP: concatenação simples dos `content` dos documentos, sem
    # sumarização/priorização por score além da ordem já devolvida pelo RAG,
    # e sem truncar por limite de tokens do modelo (ver docs/ARCHITECTURE.md
    # §5). O playbook do domínio (ver app/router/playbooks.py) é anteposto
    # quando existe; `fora_escopo` não tem playbook.
    """
    system_prompt = build_system_prompt(domain)
    partes: list[str] = []
    if system_prompt is not None:
        partes.append(system_prompt)

    if dados_catalogo is not None:
        partes.append(dados_catalogo)

    if documentos:
        contexto = "\n\n".join(f"- {documento.content}" for documento in documentos)
        partes.append(
            "Use as informações a seguir, recuperadas da base de conhecimento "
            "da empresa, para responder à mensagem do cliente. Se as "
            "informações não forem suficientes, responda com o que souber, sem "
            "inventar dados específicos (preços, prazos, números de série).\n\n"
            f"Informações recuperadas:\n{contexto}"
        )

    partes.append(f"Mensagem do cliente: {message}")
    return "\n\n".join(partes)
```

- [ ] **Step 6: Reestruturar o bloco RAG de `handle_message` com `asyncio.TaskGroup`**

Adicionar `dados_catalogo_vendas: DadosCatalogoVendas | None = None` junto às outras variáveis de tracking já inicializadas antes do `if classification.domain == "fora_escopo":` (mesmo bloco de `backend_escolhido`, `motivo`, `documentos`, `rag_retrieval_ms`, etc.).

Substituir o bloco `else:` inteiro (da busca RAG até o `prompt = _build_prompt(...)`, ver Step 0 acima) por:

```python
    else:
        t_rag_start = time.perf_counter()
        try:
            async with asyncio.TaskGroup() as tg:
                rag_task = tg.create_task(
                    _buscar_documentos_rag(
                        message, recent_messages, classification.domain, rag_client
                    )
                )
                vendas_task: asyncio.Task[DadosCatalogoVendas | None] | None = None
                if classification.domain == "vendas" and sales_catalog_client is not None:
                    # Busca RAG e consulta de vendas são independentes — rodam
                    # em paralelo (mesmo idioma já usado para tone/classify,
                    # ver docs/ARCHITECTURE.md §5, correção de 2026-09-24).
                    # `_consultar_vendas` nunca levanta (ver seu docstring),
                    # então só `rag_task` pode disparar o `except*` abaixo.
                    vendas_task = tg.create_task(
                        _consultar_vendas(
                            message, recent_messages, sales_catalog_client, local_client
                        )
                    )
        except* RAGConnectionError as eg:
            logger.error(
                "rag_indisponivel",
                extra={"router": {"event": "rag_indisponivel", "domain": classification.domain}},
            )
            # `raise eg.exceptions[0]` (não um `raise` nu) para propagar a
            # RAGConnectionError original, não um ExceptionGroup — chamadores
            # de handle_message ainda esperam `except RAGConnectionError`.
            raise eg.exceptions[0]

        documentos = rag_task.result()
        if vendas_task is not None:
            dados_catalogo_vendas = vendas_task.result()

        t_rag_end = time.perf_counter()
        rag_retrieval_ms = round((t_rag_end - t_rag_start) * 1000.0, 2)
        rag_chunks_count = len(documentos)
        if documentos:
            rag_avg_score = round(sum(d.score for d in documentos) / len(documentos), 4)
            rag_chunks = [
                RagChunkMetric(source=d.source, score=round(d.score, 4)) for d in documentos
            ]

        if not documentos:
            backend_escolhido = "externo"
            motivo = "rag_vazio"
        elif classification.complexity == "alta":
            backend_escolhido = "externo"
            motivo = "complexidade_alta"

    # A decisão de roteamento (backend_escolhido/motivo) usa só o sinal
    # vazio x não-vazio acima, sem mudar aqui; o conteúdo dos documentos
    # (quando houver) só entra a partir deste ponto, no prompt em si.
    # _build_prompt é sempre chamado para anexar o playbook do domínio (Fase
    # 3); para `fora_escopo` (sem playbook) e sem documentos, ele reduz a
    # apenas "Mensagem do cliente: ...".
    prompt = _build_prompt(
        message,
        documentos,
        classification.domain,
        dados_catalogo=(
            _formatar_dados_catalogo_vendas(dados_catalogo_vendas)
            if dados_catalogo_vendas is not None
            else None
        ),
    )
```

Nota: `rag_retrieval_ms` passa a medir o tempo do bloco paralelo inteiro (RAG + consulta de vendas, quando houver) em vez de só a busca RAG — aceitável (reflete a latência real contribuída pelas duas buscas independentes para mensagens de Vendas); não é um requisito da spec mudar isso, só um efeito colateral documentado da paralelização.

- [ ] **Step 7: Adicionar `sales_catalog_client` à assinatura de `handle_message` e os imports novos**

No topo do arquivo, adicionar aos imports já existentes:

```python
from app.router.sales_catalog import (
    DadosCatalogoVendas,
    SalesCatalogClient,
    extract_sales_slots,
    extrair_termos_busca,
)
```

Na assinatura de `handle_message`, adicionar o novo parâmetro (junto a `calendar_client`/`scheduling_config`, mesmo padrão de opcionalidade):

```python
async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    conversation_id: str = "",
    calendar_client: CalendarClient | None = None,
    scheduling_config: SchedulingConfig | None = None,
    sales_catalog_client: SalesCatalogClient | None = None,
    intent_router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER,
    tone_monitor_enabled: bool = True,
    tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision | EscalonamentoEvent]:
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd backend && uv run pytest tests/test_orchestrator.py -v`
Expected: PASS — inclusive os testes já existentes (ex.: `test_rag_vazio_escala_para_externo`, o teste que espera `pytest.raises(RAGConnectionError)`), sem nenhuma regressão.

- [ ] **Step 9: Lint**

Run: `cd backend && uv run ruff check src/app/router/orchestrator.py tests/test_orchestrator.py`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
cd backend
git add src/app/router/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(vendas): integra SalesCatalogClient no orchestrator (R12, Fase 5)"
```

---

## Task 4: Injeção de dependência (`main.py` + `chat.py`)

**Files:**
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `SalesCatalogClient` (Task 1), `app.state.db_sessionmaker` (já existe em `main.py`).

- [ ] **Step 1: `main.py` — instanciar `SalesCatalogClient`**

Adicionar o import junto aos demais de `app.router.*`:

```python
from app.router.sales_catalog import SalesCatalogClient
```

Logo após o bloco que cria `app.state.rag_client` (que já usa `app.state.db_sessionmaker`):

```python
    # Orquestrador como integrador do MCP B2B em Vendas (R12, Fase 5) — ver
    # docs/superpowers/specs/2026-09-24-orquestrador-mcp-b2b-vendas-design.md.
    # Chama app.db.catalog diretamente (mesmo processo), não abre uma
    # conexão MCP real contra o mcp-b2b-server separado (spec §4).
    app.state.sales_catalog_client = SalesCatalogClient(app.state.db_sessionmaker)
```

- [ ] **Step 2: `chat.py` — dependência e parâmetro do endpoint**

Adicionar o import:

```python
from app.router.sales_catalog import SalesCatalogClient
```

Adicionar a função de dependência, junto a `get_calendar_client`/`get_scheduling_config`:

```python
def get_sales_catalog_client(request: Request) -> SalesCatalogClient:
    return request.app.state.sales_catalog_client
```

Adicionar o parâmetro em `send_message`, junto a `calendar_client`/`scheduling_config`:

```python
    sales_catalog_client: SalesCatalogClient = Depends(get_sales_catalog_client),
```

E passar adiante na chamada a `handle_message(...)` dentro de `event_stream()`, junto a `calendar_client=calendar_client, scheduling_config=scheduling_config,`:

```python
                sales_catalog_client=sales_catalog_client,
```

- [ ] **Step 3: `test_chat_api.py` — override do novo dependency**

Adicionar `get_sales_catalog_client` ao import de `app.api.chat` no topo do arquivo (mesma lista de `get_calendar_client`, etc.).

Em `_build_app`, junto às duas linhas já existentes:

```python
    app.dependency_overrides[get_calendar_client] = lambda: None
    app.dependency_overrides[get_scheduling_config] = lambda: None
    app.dependency_overrides[get_sales_catalog_client] = lambda: None
```

`None` aqui é seguro: `handle_message` trata `sales_catalog_client=None` como "sem integração de vendas", mesmo comportamento de hoje — os testes de `test_chat_api.py` não exercitam o fluxo de vendas (isso é coberto em `test_orchestrator.py`, Task 3).

- [ ] **Step 4: Run the full backend test suite**

Run: `cd backend && uv run pytest -q`
Expected: PASS — todos os testes (incluindo `test_chat_api.py` e `test_orchestrator.py` inteiros), sem regressão.

- [ ] **Step 5: Lint**

Run: `cd backend && uv run ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 6: Marcar o item no roadmap**

Em `docs/ROADMAP.md`, trocar a caixa do item "Integrar o Roteador/Orquestrador como 'mais um integrador' do MCP B2B para intenções de Vendas (cotação, compatibilidade, estoque)" (Fase 5) de `- [ ]` para `- [x]`, com uma nota curta descrevendo o que foi feito (novo módulo `app.router.sales_catalog`, resolução em duas etapas por causa do catálogo de ~1000 produtos, chamada direta a `app.db.catalog`) e apontando para a spec.

- [ ] **Step 7: Commit**

```bash
cd backend
git add src/app/main.py src/app/api/chat.py tests/test_chat_api.py
git add ../docs/ROADMAP.md
git commit -m "feat(vendas): liga SalesCatalogClient ao endpoint de chat (R12, Fase 5)"
```

---

## Pós-implementação (não faz parte deste plano)

O último item da Fase 5 ("Garantir e documentar que autenticação por parceiro e exposição pública não fazem parte do MVP") continua pendente — é só documentação, sem código novo; considerar como próximo passo do roadmap depois deste plano, não incluído aqui.
