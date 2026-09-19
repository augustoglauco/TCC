# Crawler de Páginas para o RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o crawler de páginas do RAG (R4, Fase 2) — disparado manualmente pelo admin a partir de uma URL semente (interna ou externa), navegando por links até uma profundidade e um teto de páginas parametrizáveis por execução, classificando cada página por domínio via LLM externo e roteando por um limiar de confiança entre ingestão direta e uma fila de revisão humana.

**Architecture:** Backend: um módulo de crawling (`app.rag.crawler`, BFS com `httpx`+`BeautifulSoup`), um classificador por LLM (`app.rag.crawler_classifier`, mesmo padrão de prompt/parsing JSON de `app.router.classifier`), um passo de dedup-por-URL que reaproveita `delete_by_document_id` já existente (`app.rag.crawler_ingest`), uma tabela nova `crawler_pending_pages` para a fila de revisão, e endpoints novos sob `/api/rag/crawler`. `CRAWLER_MAX_PAGES`/`CRAWLER_CONFIDENCE_THRESHOLD` viram runtime settings (mesmo padrão de `rag_search_domain_fallback`). Frontend: nova aba "Crawler" em `/admin/ingestao` com form de disparo + tabela de revisão, reaproveitando o pipeline de ingestão (`ingest_bytes`) e os componentes de UI já existentes (`Toast`, `Tabs`).

**Tech Stack:** FastAPI, SQLAlchemy 2.0 (async) + Alembic + Postgres, Qdrant (`qdrant-client`), `httpx`, `beautifulsoup4` (nova dependência), Next.js (App Router) + Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-19-crawler-paginas-design.md`

## Global Constraints

- Navegação real (BFS) a partir de uma URL semente — **não** uma lista fixa de páginas, e **não** restrita ao próprio site da empresa (spec §"Motivação").
- `depth` e `max_pages` são parâmetros **por execução** (form/request), não fixos. `CRAWLER_MAX_PAGES` é só o valor default que pré-preenche o form — **sem teto rígido no backend** (spec §2, decisão explícita).
- BFS restrito ao mesmo host da URL semente; visited-set por URL normalizada (sem fragmento) evita loop em links de retorno (spec §2).
- Classificação de domínio por LLM externo (`OpenRouterClient`), com `confidence`. `confidence >= CRAWLER_CONFIDENCE_THRESHOLD` (default `0.7`) ingere direto; abaixo, vai para a fila de revisão — nunca ingerida "provisoriamente" (spec §1).
- Falha de parse do JSON de classificação → `confidence=0.0` (nunca assume confiança alta por omissão).
- Dedup por URL: antes de gravar pontos no Qdrant para uma URL (auto-ingestão ou aprovação manual), remove pontos + registro de uma ingestão anterior da mesma URL, se existir — via `delete_by_document_id` já existente (spec §3).
- Recrawl de uma URL ainda pendente de revisão faz **upsert** da linha existente (mesma URL, `unique`), não duplica a fila (spec §"Dedup por URL").
- `crawler_max_pages_default`/`crawler_confidence_threshold` viram parte de `RuntimeSettingsResponse`/`RuntimeSettingsUpdateRequest`, ajustáveis via `PUT /api/admin/runtime-settings` (spec §"Config nova").
- Fora de escopo desta entrega: teto rígido de `max_pages` no backend, `robots.txt`/rate limiting, histórico de páginas aprovadas/rejeitadas, agendamento/recrawl automático (spec §"Fora de escopo").

---

### Task 1: Config, dependência nova e `.env.example`

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.crawler_max_pages: int` (default `20`), `Settings.crawler_confidence_threshold: float` (default `0.7`).

- [ ] **Step 1: Escrever os testes (falhando)**

Adicionar ao final de `backend/tests/test_config.py`:

```python
def test_settings_have_crawler_defaults():
    settings = Settings(_env_file=None)
    assert settings.crawler_max_pages == 20
    assert settings.crawler_confidence_threshold == 0.7
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_config.py::test_settings_have_crawler_defaults -v`
Expected: FAIL com `AttributeError: 'Settings' object has no attribute 'crawler_max_pages'`

- [ ] **Step 3: Adicionar os campos em `Settings`**

Em `backend/src/app/config.py`, logo após o bloco `rag_uploads_dir` (antes de `google_calendar_credentials_path`):

```python
    # MVP: teto default (não rígido — o form do admin pode pedir mais por
    # execução, ver `app.api.crawler`) de páginas por execução do crawler de
    # páginas (R4). Ajustável em runtime via `PUT /api/admin/runtime-settings`
    # (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md).
    crawler_max_pages: int = 20
    # Limiar de confiança do classificador de domínio do crawler:
    # `confidence >= limiar` ingere direto, abaixo vai pra fila de revisão
    # manual. Ajustável em runtime via `PUT /api/admin/runtime-settings`.
    crawler_confidence_threshold: float = 0.7
```

- [ ] **Step 4: Adicionar `beautifulsoup4` como dependência**

Em `backend/pyproject.toml`, no array `dependencies` (depois de `"pdfplumber>=0.11",`):

```toml
    "beautifulsoup4>=4.12",
```

Run: `cd backend && .venv/bin/pip install -e ".[dev]"`

- [ ] **Step 5: Documentar as variáveis em `.env.example`**

Em `backend/.env.example`, logo após o bloco `RAG_UPLOADS_DIR` (antes do bloco PostgreSQL):

```
# --- Crawler de páginas (RAG, R4) ---
# MVP: teto default de páginas por execução — sem limite rígido no backend,
# o admin pode pedir mais por execução via form
CRAWLER_MAX_PAGES=20
# Limiar de confiança do classificador: acima ingere direto, abaixo vai pra
# fila de revisão manual
CRAWLER_CONFIDENCE_THRESHOLD=0.7
```

- [ ] **Step 6: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/config.py backend/pyproject.toml backend/.env.example backend/tests/test_config.py
git commit -m "feat(rag): adiciona config do crawler de páginas (R4, Fase 2)"
```

---

### Task 2: Modelo de dados `CrawlerPendingPage` + migração `0004`

**Files:**
- Modify: `backend/src/app/db/models.py`
- Create: `backend/migrations/versions/0004_crawler_pending_pages.py`

**Interfaces:**
- Consumes: `app.db.models.Base` (`backend/src/app/db/models.py:15`), `_JsonVariant`/padrão de colunas já usado por `RagDocument`.
- Produces: `app.db.models.CrawlerPendingPage` (`id: UUID`, `url: str unique`, `extracted_text: str`, `domain_proposed: str`, `confidence: float`, `created_at`, `updated_at`).

- [ ] **Step 1: Adicionar o modelo em `app/db/models.py`**

Ao final de `backend/src/app/db/models.py` (depois da classe `RagDocument`):

```python


class CrawlerPendingPage(Base):
    """Página crawleada com confiança de classificação abaixo do limiar,
    aguardando aprovação manual (R4, crawler de páginas) — ver
    docs/superpowers/specs/2026-09-19-crawler-paginas-design.md §"Dados".

    Deletada ao aprovar ou rejeitar — a tabela só reflete o que está
    pendente agora, sem histórico de decisões passadas. `url` é `unique`:
    recrawlear a mesma URL ainda pendente atualiza esta linha em vez de
    duplicar (upsert, ver `app.rag.crawler_pending.upsert_pending_page`).
    """

    __tablename__ = "crawler_pending_pages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    url: Mapped[str] = mapped_column(unique=True)
    extracted_text: Mapped[str]
    domain_proposed: Mapped[str]
    confidence: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 2: Criar a migração Alembic `0004`**

```python
"""create crawler_pending_pages (R4 - crawler de páginas)

# MVP: fila de revisão humana para páginas cuja classificação de domínio
teve confiança abaixo do limiar configurado — ver
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawler_pending_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("url", sa.String(), nullable=False, unique=True),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("domain_proposed", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("crawler_pending_pages")
```

- [ ] **Step 3: Rodar a migração contra o Postgres local**

Run: `cd backend && .venv/bin/alembic upgrade head`
Expected: log confirmando `0003 -> 0004`, sem erro (requer o Postgres do `docker-compose.yml` no ar).

- [ ] **Step 4: Confirmar que `Base.metadata` cria a tabela também no SQLite de teste**

Run: `cd backend && .venv/bin/python -c "
import asyncio
from app.db.engine import create_db_engine
from app.db.models import Base

async def main():
    engine = create_db_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('ok:', 'crawler_pending_pages' in Base.metadata.tables)

asyncio.run(main())
"`
Expected: `ok: True`

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0004_crawler_pending_pages.py
git commit -m "feat(rag): modelo e migração de crawler_pending_pages (R4, Fase 2)"
```

---

### Task 3: `app.rag.crawler` — fetch, extração de HTML e BFS

**Files:**
- Create: `backend/src/app/rag/crawler.py`
- Test: `backend/tests/test_rag_crawler.py`

**Interfaces:**
- Produces: `app.rag.crawler.FetchedPage` (`url: str`, `text: str`, `links: list[str]`), `app.rag.crawler.CrawlResult` (`pages: list[FetchedPage]`, `errors: list[str]`), `app.rag.crawler.extract_text_and_links(html: str, base_url: str) -> tuple[str, list[str]]`, `app.rag.crawler.fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage | None`, `app.rag.crawler.crawl(client: httpx.AsyncClient, seed_url: str, depth: int, max_pages: int) -> CrawlResult`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `backend/tests/test_rag_crawler.py`:

```python
import httpx
import pytest

from app.rag.crawler import crawl, extract_text_and_links, fetch_page


def test_extract_text_and_links_remove_script_style_nav_footer():
    html = """
    <html><body>
      <nav>menu</nav>
      <script>var x = 1;</script>
      <style>.a{color:red}</style>
      <main><h1>Título</h1><p>Conteúdo real da página.</p></main>
      <footer>rodapé</footer>
    </body></html>
    """

    text, _links = extract_text_and_links(html, "https://exemplo.com")

    assert "menu" not in text
    assert "rodapé" not in text
    assert "var x" not in text
    assert "Título" in text
    assert "Conteúdo real da página." in text


def test_extract_text_and_links_resolve_links_relativos_e_absolutos():
    html = """
    <html><body>
      <a href="/produtos">Produtos</a>
      <a href="https://exemplo.com/suporte#faq">Suporte</a>
      <a href="https://outrosite.com/x">Externo</a>
    </body></html>
    """

    _text, links = extract_text_and_links(html, "https://exemplo.com/")

    assert "https://exemplo.com/produtos" in links
    # fragmento (#faq) é removido pela normalização
    assert "https://exemplo.com/suporte" in links
    assert "https://outrosite.com/x" in links


def _mock_transport(paginas: dict[str, tuple[int, str, str]]) -> httpx.MockTransport:
    """`paginas`: url -> (status_code, content_type, corpo)."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in paginas:
            return httpx.Response(404)
        status_code, content_type, corpo = paginas[url]
        return httpx.Response(status_code, headers={"content-type": content_type}, text=corpo)

    return httpx.MockTransport(handler)


async def test_fetch_page_retorna_none_em_erro_http():
    client = httpx.AsyncClient(transport=_mock_transport({}))

    page = await fetch_page(client, "https://exemplo.com/inexistente")

    assert page is None


async def test_fetch_page_retorna_none_para_content_type_nao_html():
    transport = _mock_transport(
        {"https://exemplo.com/arquivo.pdf": (200, "application/pdf", "binario")}
    )
    client = httpx.AsyncClient(transport=transport)

    page = await fetch_page(client, "https://exemplo.com/arquivo.pdf")

    assert page is None


async def test_fetch_page_retorna_pagina_com_texto_e_links():
    html = '<html><body><p>Olá</p><a href="/outra">Outra</a></body></html>'
    transport = _mock_transport({"https://exemplo.com/": (200, "text/html", html)})
    client = httpx.AsyncClient(transport=transport)

    page = await fetch_page(client, "https://exemplo.com/")

    assert page is not None
    assert "Olá" in page.text
    assert page.links == ["https://exemplo.com/outra"]


def _site_com_grafo_de_links() -> dict[str, tuple[int, str, str]]:
    """Grafo: home -> a -> b -> home (link de retorno), e home -> externo (outro host)."""
    home = (
        200,
        "text/html",
        '<html><body>home <a href="/a">a</a> '
        '<a href="https://outrosite.com/x">externo</a></body></html>',
    )
    pagina_a = (200, "text/html", '<html><body>pagina a <a href="/b">b</a></body></html>')
    pagina_b = (
        200,
        "text/html",
        '<html><body>pagina b <a href="/">home de novo</a></body></html>',
    )
    return {
        "https://exemplo.com/": home,
        "https://exemplo.com/a": pagina_a,
        "https://exemplo.com/b": pagina_b,
    }


async def test_crawl_respeita_profundidade():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=1, max_pages=10)

    urls = {page.url for page in result.pages}
    assert urls == {"https://exemplo.com/", "https://exemplo.com/a"}


async def test_crawl_respeita_max_pages():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=2)

    assert len(result.pages) == 2


async def test_crawl_nao_segue_host_diferente():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    urls = {page.url for page in result.pages}
    assert "https://outrosite.com/x" not in urls


async def test_crawl_evita_loop_com_link_de_retorno():
    transport = _mock_transport(_site_com_grafo_de_links())
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    urls = [page.url for page in result.pages]
    assert len(urls) == len(set(urls))
    assert urls.count("https://exemplo.com/") == 1


async def test_crawl_registra_erro_e_continua():
    paginas = _site_com_grafo_de_links()
    paginas["https://exemplo.com/a"] = (500, "text/html", "erro interno")
    transport = _mock_transport(paginas)
    client = httpx.AsyncClient(transport=transport)

    result = await crawl(client, "https://exemplo.com/", depth=5, max_pages=10)

    assert "https://exemplo.com/a" in result.errors
    urls = {page.url for page in result.pages}
    assert "https://exemplo.com/" in urls
    # "b" só é alcançável a partir de "a", que falhou — não é visitada
    assert "https://exemplo.com/b" not in urls
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.crawler'`

- [ ] **Step 3: Implementar `app/rag/crawler.py`**

```python
"""Crawler HTTP para o RAG (R4, Fase 2) — navegação BFS a partir de uma URL
semente, com profundidade e teto de páginas parametrizáveis por execução.

# MVP: execução síncrona por chamada, sem fila de background nem
agendamento — ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md
§2. Só processa respostas `text/html`; outros tipos de conteúdo (imagem, PDF
linkado) são ignorados nesta entrega (RAG multimodal é Fase 3).
"""

from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

_FETCH_TIMEOUT_S = 10.0
_IGNORED_TAGS = ("script", "style", "nav", "footer")


@dataclass
class FetchedPage:
    url: str
    text: str
    links: list[str] = field(default_factory=list)


@dataclass
class CrawlResult:
    pages: list[FetchedPage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _normalize_url(url: str) -> str:
    """Remove o fragmento (`#...`) — necessário para o visited-set do BFS
    tratar âncoras diferentes da mesma página como a mesma URL."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def extract_text_and_links(html: str, base_url: str) -> tuple[str, list[str]]:
    """Extrai texto visível (sem `script`/`style`/`nav`/`footer`) e os links
    (`<a href>`) resolvidos para absoluto via `urljoin` e normalizados."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_IGNORED_TAGS):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    links = [_normalize_url(urljoin(base_url, a["href"])) for a in soup.find_all("a", href=True)]
    return text, links


async def fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage | None:
    """Busca `url`; devolve `None` (sem levantar) em qualquer falha de
    rede/timeout/status não-2xx/content-type não-HTML — cabe ao chamador
    (`crawl`) decidir registrar o erro."""
    try:
        response = await client.get(url, timeout=_FETCH_TIMEOUT_S, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return None
    text, links = extract_text_and_links(response.text, url)
    return FetchedPage(url=url, text=text, links=links)


async def crawl(client: httpx.AsyncClient, seed_url: str, depth: int, max_pages: int) -> CrawlResult:
    """BFS a partir de `seed_url`, restrito ao mesmo host, até `depth`
    saltos ou `max_pages` páginas visitadas (o que vier primeiro).
    Visited-set por URL normalizada evita loop em links de retorno."""
    seed_normalizada = _normalize_url(seed_url)
    seed_host = urlparse(seed_normalizada).netloc

    result = CrawlResult()
    visited: set[str] = set()
    fila: list[tuple[str, int]] = [(seed_normalizada, 0)]

    while fila and len(result.pages) < max_pages:
        url, nivel = fila.pop(0)
        if url in visited:
            continue
        visited.add(url)

        page = await fetch_page(client, url)
        if page is None:
            result.errors.append(url)
            continue

        result.pages.append(page)

        if nivel >= depth:
            continue
        for link in page.links:
            if link not in visited and urlparse(link).netloc == seed_host:
                fila.append((link, nivel + 1))

    return result
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/crawler.py backend/tests/test_rag_crawler.py
git commit -m "feat(rag): BFS do crawler de páginas com fetch/extração de HTML (R4, Fase 2)"
```

---

### Task 4: `app.rag.crawler_classifier` — classificação de domínio por LLM

**Files:**
- Create: `backend/src/app/rag/crawler_classifier.py`
- Test: `backend/tests/test_rag_crawler_classifier.py`

**Interfaces:**
- Consumes: `app.router.llm_client.LLMClient` (`backend/src/app/router/llm_client.py:44`, método `generate(prompt: str) -> LLMResponse`), `app.models.rag.RagDomain`.
- Produces: `app.rag.crawler_classifier.PageClassification` (`domain: RagDomain`, `confidence: float`), `app.rag.crawler_classifier.classify_page(llm_client: LLMClient, text: str) -> PageClassification`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `backend/tests/test_rag_crawler_classifier.py`:

```python
from app.router.llm_client import LLMResponse
from app.rag.crawler_classifier import classify_page


class _FakeLLMClient:
    def __init__(self, texto_resposta: str) -> None:
        self._texto_resposta = texto_resposta

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._texto_resposta, total_duration_ms=1.0)

    def generate_stream(self, prompt: str):
        raise NotImplementedError

    async def is_model_ready(self) -> bool:
        return True


async def test_classify_page_json_valido():
    llm = _FakeLLMClient('{"domain": "suporte", "confidence": 0.92}')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.domain == "suporte"
    assert resultado.confidence == 0.92


async def test_classify_page_com_code_fence():
    llm = _FakeLLMClient('```json\n{"domain": "vendas", "confidence": 0.8}\n```')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.domain == "vendas"
    assert resultado.confidence == 0.8


async def test_classify_page_json_malformado_confidence_zero():
    llm = _FakeLLMClient("não é json")

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.confidence == 0.0


async def test_classify_page_domain_invalido_confidence_zero():
    llm = _FakeLLMClient('{"domain": "financeiro", "confidence": 0.9}')

    resultado = await classify_page(llm, "conteúdo da página")

    assert resultado.confidence == 0.0
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_classifier.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.crawler_classifier'`

- [ ] **Step 3: Implementar `app/rag/crawler_classifier.py`**

```python
"""Classificação de domínio de páginas crawleadas via LLM externo (R4,
Fase 2) — mesmo padrão de prompt/parsing de `app.router.classifier`, mas
devolvendo também uma confiança, usada pelo gate de auto-ingestão x fila de
revisão (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md
§1).
"""

import json
import re
from typing import get_args

from pydantic import BaseModel, ValidationError

from app.models.rag import RagDomain
from app.router.llm_client import LLMClient

_PROMPT_TEMPLATE = """\
Classifique o conteúdo de uma página de site em UM dos domínios: vendas, \
suporte, atendimento. Avalie também sua confiança nessa classificação, de \
0.0 (nenhuma certeza) a 1.0 (certeza total).

Conteúdo da página:
{texto}

Responda apenas com JSON no formato: {{"domain": "...", "confidence": 0.0}}"""

# MVP: corte simples do texto extraído da página inteira antes de enviar ao
# LLM — a classificação é por página, não por chunk (sem chunking prévio
# aqui, diferente do pipeline de ingestão em si).
_MAX_PROMPT_CHARS = 4000

_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)

_FALLBACK_DOMAIN: RagDomain = get_args(RagDomain)[0]


class PageClassification(BaseModel):
    domain: RagDomain
    confidence: float


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


async def classify_page(llm_client: LLMClient, text: str) -> PageClassification:
    """Classifica o texto de uma página crawleada. Qualquer falha de parse
    do JSON devolvido pelo LLM (ou `domain` fora de `RagDomain`) vira
    `confidence=0.0` — nunca assume confiança alta por omissão; o `domain`
    de fallback é só um placeholder (a página cai na fila de revisão, onde
    o domain é editável antes de aprovar)."""
    prompt = _PROMPT_TEMPLATE.format(texto=text[:_MAX_PROMPT_CHARS])
    response = await llm_client.generate(prompt)
    try:
        parsed = json.loads(_strip_code_fence(response.text))
        return PageClassification(**parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return PageClassification(domain=_FALLBACK_DOMAIN, confidence=0.0)
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_classifier.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/crawler_classifier.py backend/tests/test_rag_crawler_classifier.py
git commit -m "feat(rag): classificação de domínio por LLM para páginas crawleadas (R4, Fase 2)"
```

---

### Task 5: `app.rag.crawler_pending` — CRUD da fila de revisão

**Files:**
- Create: `backend/src/app/rag/crawler_pending.py`
- Test: `backend/tests/test_rag_crawler_pending.py`

**Interfaces:**
- Consumes: `app.db.models.CrawlerPendingPage` (Task 2), fixture `db_session` (`backend/tests/conftest.py:188`).
- Produces: `app.rag.crawler_pending.upsert_pending_page(session, *, url, extracted_text, domain_proposed, confidence) -> CrawlerPendingPage`, `list_pending_pages(session) -> list[CrawlerPendingPage]`, `get_pending_page(session, page_id: uuid.UUID) -> CrawlerPendingPage | None`, `delete_pending_page(session, page_id: uuid.UUID) -> bool`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `backend/tests/test_rag_crawler_pending.py`:

```python
import uuid

from app.rag.crawler_pending import (
    delete_pending_page,
    get_pending_page,
    list_pending_pages,
    upsert_pending_page,
)


async def test_upsert_pending_page_cria_nova_linha(db_session):
    page = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="conteúdo da página",
        domain_proposed="vendas",
        confidence=0.4,
    )

    assert page.url == "https://exemplo.com/produtos"
    assert page.domain_proposed == "vendas"
    assert page.confidence == 0.4


async def test_upsert_pending_page_atualiza_existente_mesma_url(db_session):
    original = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="texto v1",
        domain_proposed="vendas",
        confidence=0.4,
    )

    atualizada = await upsert_pending_page(
        db_session,
        url="https://exemplo.com/produtos",
        extracted_text="texto v2",
        domain_proposed="suporte",
        confidence=0.5,
    )

    assert atualizada.id == original.id
    assert atualizada.extracted_text == "texto v2"
    assert atualizada.domain_proposed == "suporte"
    todas = await list_pending_pages(db_session)
    assert len(todas) == 1


async def test_list_pending_pages_ordenado_mais_recente_primeiro(db_session):
    await upsert_pending_page(
        db_session, url="https://exemplo.com/a", extracted_text="a", domain_proposed="vendas", confidence=0.1
    )
    await upsert_pending_page(
        db_session, url="https://exemplo.com/b", extracted_text="b", domain_proposed="vendas", confidence=0.1
    )

    paginas = await list_pending_pages(db_session)

    assert [p.url for p in paginas] == ["https://exemplo.com/b", "https://exemplo.com/a"]


async def test_get_pending_page_inexistente_retorna_none(db_session):
    assert await get_pending_page(db_session, uuid.uuid4()) is None


async def test_delete_pending_page_remove_e_retorna_true(db_session):
    page = await upsert_pending_page(
        db_session, url="https://exemplo.com/a", extracted_text="a", domain_proposed="vendas", confidence=0.1
    )

    removida = await delete_pending_page(db_session, page.id)

    assert removida is True
    assert await get_pending_page(db_session, page.id) is None


async def test_delete_pending_page_inexistente_retorna_false(db_session):
    assert await delete_pending_page(db_session, uuid.uuid4()) is False
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_pending.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.crawler_pending'`

- [ ] **Step 3: Implementar `app/rag/crawler_pending.py`**

```python
"""CRUD da fila de revisão de páginas crawleadas (R4, Fase 2) — sobre
`app.db.models.CrawlerPendingPage`. Mesmo padrão de `app.rag.registry`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlerPendingPage


async def upsert_pending_page(
    session: AsyncSession,
    *,
    url: str,
    extracted_text: str,
    domain_proposed: str,
    confidence: float,
) -> CrawlerPendingPage:
    """Cria a linha pendente para `url`, ou atualiza a existente (mesma URL
    recrawleada antes de alguém revisar) — evita fila duplicada pra mesma
    URL (spec §"Dedup por URL")."""
    result = await session.execute(select(CrawlerPendingPage).where(CrawlerPendingPage.url == url))
    existing = result.scalars().first()
    if existing is not None:
        existing.extracted_text = extracted_text
        existing.domain_proposed = domain_proposed
        existing.confidence = confidence
        await session.commit()
        await session.refresh(existing)
        return existing

    page = CrawlerPendingPage(
        id=uuid.uuid4(),
        url=url,
        extracted_text=extracted_text,
        domain_proposed=domain_proposed,
        confidence=confidence,
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page


async def list_pending_pages(session: AsyncSession) -> list[CrawlerPendingPage]:
    result = await session.execute(
        select(CrawlerPendingPage).order_by(CrawlerPendingPage.created_at.desc())
    )
    return list(result.scalars().all())


async def get_pending_page(session: AsyncSession, page_id: uuid.UUID) -> CrawlerPendingPage | None:
    return await session.get(CrawlerPendingPage, page_id)


async def delete_pending_page(session: AsyncSession, page_id: uuid.UUID) -> bool:
    page = await session.get(CrawlerPendingPage, page_id)
    if page is None:
        return False
    await session.delete(page)
    await session.commit()
    return True
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_pending.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/crawler_pending.py backend/tests/test_rag_crawler_pending.py
git commit -m "feat(rag): CRUD da fila de revisão do crawler (R4, Fase 2)"
```

---

### Task 6: `app.rag.crawler_ingest` — dedup por URL + gate de confiança

**Files:**
- Create: `backend/src/app/rag/crawler_ingest.py`
- Test: `backend/tests/test_rag_crawler_ingest.py`

**Interfaces:**
- Consumes: `app.rag.ingest.ingest_bytes` (`backend/src/app/rag/ingest.py:80`), `app.rag.registry.delete_document` (`backend/src/app/rag/registry.py:63`), `app.rag.crawler_pending.upsert_pending_page` (Task 5), `app.rag.crawler_classifier.PageClassification` (Task 4), fixtures `db_session`/`active_collection`/`_FakeQdrantRAGClient` (`backend/tests/conftest.py`).
- Produces: `app.rag.crawler_ingest.replace_previous_ingestion(session, qdrant, collection, url) -> None`, `app.rag.crawler_ingest.ingest_or_queue(session, qdrant, collection, embedder, uploads_dir, url, text, classification, confidence_threshold) -> Literal["ingested", "queued"]`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `backend/tests/test_rag_crawler_ingest.py`:

```python
from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_ingest import ingest_or_queue, replace_previous_ingestion
from app.rag.crawler_pending import list_pending_pages
from app.rag.registry import list_documents
from tests.conftest import _FakeQdrantRAGClient


async def test_replace_previous_ingestion_noop_quando_nunca_ingerido(db_session, active_collection):
    fake = _FakeQdrantRAGClient()

    await replace_previous_ingestion(db_session, fake, active_collection, "https://exemplo.com/a")

    assert fake.deleted == []


async def test_ingest_or_queue_confidence_alta_ingere(db_session, active_collection, tmp_path):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.9)

    outcome = await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/produtos",
        "conteúdo da página de produtos",
        classification,
        confidence_threshold=0.7,
    )

    assert outcome == "ingested"
    assert len(fake.upserts) == 1
    _collection_name, _chunks, source, domain, _document_id = fake.upserts[0]
    assert (source, domain) == ("https://exemplo.com/produtos", "vendas")
    assert await list_pending_pages(db_session) == []


async def test_ingest_or_queue_confidence_baixa_enfileira(db_session, active_collection, tmp_path):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.3)

    outcome = await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/ambiguo",
        "conteúdo ambíguo",
        classification,
        confidence_threshold=0.7,
    )

    assert outcome == "queued"
    assert fake.upserts == []
    pendentes = await list_pending_pages(db_session)
    assert len(pendentes) == 1
    assert pendentes[0].url == "https://exemplo.com/ambiguo"


async def test_ingest_or_queue_recrawl_url_ja_ingerida_substitui(db_session, active_collection, tmp_path):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.9)

    await ingest_or_queue(
        db_session, fake, active_collection, embedder, tmp_path,
        "https://exemplo.com/produtos", "versão 1", classification, confidence_threshold=0.7,
    )
    primeiro_document_id = fake.upserts[0][4]

    await ingest_or_queue(
        db_session, fake, active_collection, embedder, tmp_path,
        "https://exemplo.com/produtos", "versão 2", classification, confidence_threshold=0.7,
    )

    assert fake.deleted == [(active_collection.name, primeiro_document_id)]
    documentos = await list_documents(db_session)
    assert len(documentos) == 1
    assert documentos[0].filename == "https://exemplo.com/produtos"
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_ingest.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.rag.crawler_ingest'`

- [ ] **Step 3: Implementar `app/rag/crawler_ingest.py`**

```python
"""Ingestão (ou enfileiramento) de páginas crawleadas no RAG (R4, Fase 2) —
aplica o gate de confiança e o passo de dedup-por-URL descritos em
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md §1, §3.
"""

from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument
from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_pending import upsert_pending_page
from app.rag.embeddings import TextEmbedder
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document

_CRAWLER_ORIGIN = "crawler"


async def replace_previous_ingestion(
    session: AsyncSession,
    qdrant: QdrantRAGClient,
    collection: RagCollection,
    url: str,
) -> None:
    """Remove pontos + registro de uma ingestão anterior da mesma `url`
    nesta `collection`, se existir — evita duplicar pontos no Qdrant ao
    recrawlear (spec §3). No-op se a URL nunca foi ingerida antes."""
    result = await session.execute(
        select(RagDocument).where(
            RagDocument.filename == url,
            RagDocument.collection_id == collection.id,
            RagDocument.origin == _CRAWLER_ORIGIN,
        )
    )
    documento_anterior = result.scalars().first()
    if documento_anterior is None:
        return
    await qdrant.delete_by_document_id(collection.name, str(documento_anterior.id))
    await delete_document(session, str(documento_anterior.id))


async def ingest_or_queue(
    session: AsyncSession,
    qdrant: QdrantRAGClient,
    collection: RagCollection,
    embedder: TextEmbedder,
    uploads_dir: Path,
    url: str,
    text: str,
    classification: PageClassification,
    confidence_threshold: float,
) -> Literal["ingested", "queued"]:
    """Aplica o gate de confiança: `confidence >= confidence_threshold`
    ingere direto (com dedup-por-URL antes); abaixo do limiar, upsert na
    fila de revisão (`crawler_pending_pages`), fora do RAG até aprovação."""
    if classification.confidence >= confidence_threshold:
        await replace_previous_ingestion(session, qdrant, collection, url)
        await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename=url,
            content=text.encode("utf-8"),
            domain=classification.domain,
            session=session,
            origin=_CRAWLER_ORIGIN,
        )
        return "ingested"

    await upsert_pending_page(
        session,
        url=url,
        extracted_text=text,
        domain_proposed=classification.domain,
        confidence=classification.confidence,
    )
    return "queued"
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_rag_crawler_ingest.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/rag/crawler_ingest.py backend/tests/test_rag_crawler_ingest.py
git commit -m "feat(rag): dedup por URL e gate de confiança na ingestão do crawler (R4, Fase 2)"
```

---

### Task 7: Runtime settings — `crawler_max_pages_default`/`crawler_confidence_threshold`

**Files:**
- Modify: `backend/src/app/models/runtime_settings.py`
- Modify: `backend/src/app/api/runtime_settings.py`
- Modify: `backend/src/app/main.py`
- Modify: `backend/tests/test_runtime_settings_api.py`

**Interfaces:**
- Produces: `RuntimeSettingsResponse.crawler_max_pages_default: int`, `RuntimeSettingsResponse.crawler_confidence_threshold: float` (e os mesmos em `RuntimeSettingsUpdateRequest`, opcionais). Lidos/escritos em `request.app.state.crawler_max_pages_default`/`request.app.state.crawler_confidence_threshold`.

- [ ] **Step 1: Atualizar os testes existentes (falhando)**

Em `backend/tests/test_runtime_settings_api.py`, substituir `_build_app`/`_build_default_app` e as asserções que checam o JSON completo:

```python
def _build_app(
    local_client: _FakeLocalClient,
    external_client: _FakeExternalClient,
    qdrant_client: _FakeQdrantClient,
    crawler_max_pages_default: int = 20,
    crawler_confidence_threshold: float = 0.7,
) -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_settings_router)
    app.state.local_client = local_client
    app.state.external_client = external_client
    app.state.qdrant_client = qdrant_client
    app.state.crawler_max_pages_default = crawler_max_pages_default
    app.state.crawler_confidence_threshold = crawler_confidence_threshold
    return app


def _build_default_app() -> tuple[
    FastAPI, _FakeLocalClient, _FakeExternalClient, _FakeQdrantClient
]:
    local_client = _FakeLocalClient(temperature=None, timeout_s=30.0)
    external_client = _FakeExternalClient(timeout_s=30.0)
    qdrant_client = _FakeQdrantClient(search_domain_fallback=False)
    return (
        _build_app(local_client, external_client, qdrant_client),
        local_client,
        external_client,
        qdrant_client,
    )
```

Atualizar `test_get_devolve_valores_atuais_dos_clientes` para incluir os dois campos novos no dicionário esperado:

```python
def test_get_devolve_valores_atuais_dos_clientes():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings")

    assert response.status_code == 200
    assert response.json() == {
        "local_llm_temperature": None,
        "local_llm_timeout_s": 30.0,
        "external_llm_timeout_s": 30.0,
        "rag_search_domain_fallback": False,
        "crawler_max_pages_default": 20,
        "crawler_confidence_threshold": 0.7,
    }
```

Adicionar ao final do arquivo:

```python
def test_put_atualiza_crawler_max_pages_default():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"crawler_max_pages_default": 50})

    assert response.status_code == 200
    assert response.json()["crawler_max_pages_default"] == 50
    assert app.state.crawler_max_pages_default == 50


def test_put_atualiza_crawler_confidence_threshold():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"crawler_confidence_threshold": 0.5})

    assert response.status_code == 200
    assert response.json()["crawler_confidence_threshold"] == 0.5
    assert app.state.crawler_confidence_threshold == 0.5


def test_put_crawler_confidence_threshold_fora_do_intervalo_e_422():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"crawler_confidence_threshold": 1.5})

    assert response.status_code == 422


def test_put_crawler_max_pages_default_zero_ou_negativo_e_422():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"crawler_max_pages_default": 0})

    assert response.status_code == 422
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_runtime_settings_api.py -v`
Expected: FAIL — `test_get_devolve_valores_atuais_dos_clientes` quebra por `ValidationError` (campos obrigatórios ausentes em `RuntimeSettingsResponse`), os testes novos falham por `422`/`KeyError`.

- [ ] **Step 3: Atualizar `app/models/runtime_settings.py`**

```python
"""Schemas Pydantic dos parâmetros de execução ajustáveis em runtime (além do
MVP) — mesmo padrão de `app.api.local_models` (só em memória, não persiste
entre restarts do processo). Ver decisão registrada em
docs/ARCHITECTURE.md §5.
"""

from pydantic import BaseModel, Field


class RuntimeSettingsResponse(BaseModel):
    local_llm_temperature: float | None = Field(
        default=None, description="Temperatura do Ollama; null usa o default do próprio modelo."
    )
    local_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao Ollama (classificação)."
    )
    external_llm_timeout_s: float = Field(
        ..., description="Timeout da chamada não-streaming ao OpenRouter, quando escalada."
    )
    rag_search_domain_fallback: bool = Field(
        ...,
        description="Se a busca do RAG refaz sem filtro de domínio quando a filtrada vem vazia.",
    )
    crawler_max_pages_default: int = Field(
        ..., description="Teto default de páginas por execução do crawler, pré-preenche o form do admin."
    )
    crawler_confidence_threshold: float = Field(
        ...,
        description=(
            "Limiar de confiança do classificador do crawler: acima ingere direto, "
            "abaixo vai pra fila de revisão."
        ),
    )


class RuntimeSettingsUpdateRequest(BaseModel):
    """Atualização parcial — só os campos enviados são alterados."""

    local_llm_temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    local_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    external_llm_timeout_s: float | None = Field(default=None, gt=0.0, le=300.0)
    rag_search_domain_fallback: bool | None = None
    crawler_max_pages_default: int | None = Field(default=None, ge=1)
    crawler_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
```

- [ ] **Step 4: Atualizar `app/api/runtime_settings.py`**

```python
"""Endpoint HTTP dos parâmetros de execução ajustáveis em runtime (além do
MVP) — temperatura do Ollama, timeouts dos backends local/externo, a flag
de fallback de domínio do RAG, e o teto default/limiar de confiança do
crawler de páginas. Mesmo padrão do gerenciador de modelos locais
(`app.api.local_models`): valores só em memória (`request.app.state.*`),
resetam a cada restart do processo. Ver decisão registrada em
docs/ARCHITECTURE.md §5.
"""

from fastapi import APIRouter, Request

from app.models.runtime_settings import RuntimeSettingsResponse, RuntimeSettingsUpdateRequest
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient

router = APIRouter(prefix="/api/admin/runtime-settings", tags=["runtime-settings"])


def _get_clients(
    request: Request,
) -> tuple[OllamaClient, OpenRouterClient, QdrantRAGClient]:
    return (
        request.app.state.local_client,
        request.app.state.external_client,
        request.app.state.qdrant_client,
    )


def _build_response(request: Request) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)
    return RuntimeSettingsResponse(
        local_llm_temperature=local_client.temperature,
        local_llm_timeout_s=local_client.timeout_s,
        external_llm_timeout_s=external_client.timeout_s,
        rag_search_domain_fallback=qdrant_client.search_domain_fallback,
        crawler_max_pages_default=request.app.state.crawler_max_pages_default,
        crawler_confidence_threshold=request.app.state.crawler_confidence_threshold,
    )


@router.get("", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(request: Request) -> RuntimeSettingsResponse:
    return _build_response(request)


@router.put("", response_model=RuntimeSettingsResponse)
async def update_runtime_settings(
    request: Request, body: RuntimeSettingsUpdateRequest
) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)

    # `exclude_unset` distingue "campo não enviado" (não mexe) de "campo
    # enviado com valor, inclusive null" (aplica) — permite ao cliente
    # voltar `local_llm_temperature` para `null` (usa o default do próprio
    # modelo) mandando o campo explicitamente, sem afetar os demais campos
    # não enviados nesta chamada.
    campos = body.model_dump(exclude_unset=True)

    if "local_llm_temperature" in campos:
        local_client.temperature = campos["local_llm_temperature"]
    if "local_llm_timeout_s" in campos:
        local_client.timeout_s = campos["local_llm_timeout_s"]
    if "external_llm_timeout_s" in campos:
        external_client.timeout_s = campos["external_llm_timeout_s"]
    if "rag_search_domain_fallback" in campos:
        qdrant_client.search_domain_fallback = campos["rag_search_domain_fallback"]
    if "crawler_max_pages_default" in campos:
        request.app.state.crawler_max_pages_default = campos["crawler_max_pages_default"]
    if "crawler_confidence_threshold" in campos:
        request.app.state.crawler_confidence_threshold = campos["crawler_confidence_threshold"]

    return _build_response(request)
```

- [ ] **Step 5: Seedar os valores iniciais em `app/main.py`**

Em `backend/src/app/main.py`, logo após a linha `app.state.rag_uploads_dir = Path(settings.rag_uploads_dir)`:

```python
    app.state.crawler_max_pages_default = settings.crawler_max_pages
    app.state.crawler_confidence_threshold = settings.crawler_confidence_threshold
```

- [ ] **Step 6: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_runtime_settings_api.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/models/runtime_settings.py backend/src/app/api/runtime_settings.py backend/src/app/main.py backend/tests/test_runtime_settings_api.py
git commit -m "feat(rag): expõe teto/limiar do crawler via runtime-settings (R4, Fase 2)"
```

---

### Task 8: Schemas Pydantic dos endpoints do crawler

**Files:**
- Create: `backend/src/app/models/crawler.py`

**Interfaces:**
- Consumes: `app.models.rag.RagDomain` (`backend/src/app/models/rag.py:18`).
- Produces: `app.models.crawler.CrawlRunRequest` (`url: HttpUrl`, `depth: int`, `max_pages: int | None`), `CrawlRunResponse` (`pages_visited`, `auto_ingested`, `queued`, `errors`), `PendingPageResponse` (`id`, `url`, `text_snippet`, `domain_proposed`, `confidence`, `created_at`), `ApprovePendingPageRequest` (`domain: RagDomain`), `ApprovedPageResponse` (`url`, `domain`, `chunks`).

Este módulo é só schema (sem lógica) — não precisa de teste próprio; é exercitado pelos testes de `app.api.crawler` (Task 9).

- [ ] **Step 1: Criar `app/models/crawler.py`**

```python
"""Schemas Pydantic dos endpoints do crawler de páginas do RAG (R4, Fase 2)
— ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.rag import RagDomain


class CrawlRunRequest(BaseModel):
    """Corpo de `POST /api/rag/crawler/run`. `max_pages` ausente usa o
    default configurado (`crawler_max_pages_default`, runtime settings) —
    sem teto rígido no backend (spec §2, decisão explícita)."""

    url: HttpUrl
    depth: int = Field(..., ge=0)
    max_pages: int | None = Field(default=None, ge=1)


class CrawlRunResponse(BaseModel):
    pages_visited: int
    auto_ingested: list[str]
    queued: list[str]
    errors: list[str]


class PendingPageResponse(BaseModel):
    id: UUID
    url: str
    text_snippet: str
    domain_proposed: RagDomain
    confidence: float
    created_at: datetime


class ApprovePendingPageRequest(BaseModel):
    domain: RagDomain


class ApprovedPageResponse(BaseModel):
    url: str
    domain: RagDomain
    chunks: int
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/app/models/crawler.py
git commit -m "feat(rag): schemas Pydantic dos endpoints do crawler (R4, Fase 2)"
```

---

### Task 9: `app.api.crawler` — endpoints `/run`, `/pending`, `/approve`, `/reject`

**Files:**
- Create: `backend/src/app/api/crawler.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_crawler_api.py`

**Interfaces:**
- Consumes: `app.rag.crawler.crawl` (Task 3), `app.rag.crawler_classifier.classify_page` (Task 4), `app.rag.crawler_pending.{list_pending_pages,get_pending_page,delete_pending_page}` (Task 5), `app.rag.crawler_ingest.{ingest_or_queue,replace_previous_ingestion}` (Task 6), `app.models.crawler.*` (Task 8), `app.api.rag_dependencies.{get_db_session,get_embedder_registry,get_qdrant_client,get_uploads_dir}` (`backend/src/app/api/rag_dependencies.py`), `app.rag.collections_registry.get_active_collection` (`backend/src/app/rag/collections_registry.py:80`), `app.rag.ingest.ingest_bytes` (Task 6).
- Produces: `app.api.crawler.router` (`prefix="/api/rag/crawler"`), registrado em `app.main.create_app`.

- [ ] **Step 1: Escrever os testes (falhando)**

Criar `backend/tests/test_crawler_api.py`:

```python
import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.crawler import router as crawler_router
from app.api.rag_dependencies import (
    get_db_session,
    get_embedder_registry,
    get_qdrant_client,
    get_uploads_dir,
)
from app.rag.embedders_registry import EmbedderRegistry
from app.router.llm_client import LLMResponse
from tests.conftest import _FakeQdrantRAGClient


class _FakeLLMClient:
    """Devolve sempre a mesma classificação — suficiente para os testes de
    endpoint, que não exercitam a lógica de parsing em si (já coberta por
    `test_rag_crawler_classifier.py`)."""

    def __init__(self, domain: str, confidence: float) -> None:
        self._resposta = json.dumps({"domain": domain, "confidence": confidence})

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._resposta, total_duration_ms=1.0)

    def generate_stream(self, prompt: str):
        raise NotImplementedError

    async def is_model_ready(self) -> bool:
        return True


def _mock_transport(paginas: dict[str, tuple[int, str, str]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url not in paginas:
            return httpx.Response(404)
        status_code, content_type, corpo = paginas[url]
        return httpx.Response(status_code, headers={"content-type": content_type}, text=corpo)

    return httpx.MockTransport(handler)


def _build_app(
    qdrant,
    db_session,
    uploads_dir,
    llm_client,
    max_pages_default: int = 20,
    confidence_threshold: float = 0.7,
    paginas: dict[str, tuple[int, str, str]] | None = None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(crawler_router)
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embedder_registry] = lambda: EmbedderRegistry()
    app.dependency_overrides[get_uploads_dir] = lambda: uploads_dir
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.state.external_client = llm_client
    app.state.crawler_http_client = httpx.AsyncClient(transport=_mock_transport(paginas or {}))
    app.state.crawler_max_pages_default = max_pages_default
    app.state.crawler_confidence_threshold = confidence_threshold
    return app


def test_run_confidence_alta_ingere_direto(db_session, active_collection, tmp_path):
    html = '<html><body><p>Conteúdo de vendas</p></body></html>'
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    app = _build_app(
        fake_qdrant, db_session, tmp_path, llm,
        paginas={"https://exemplo.com/": (200, "text/html", html)},
    )
    client = TestClient(app)

    response = client.post("/api/rag/crawler/run", json={"url": "https://exemplo.com/", "depth": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["pages_visited"] == 1
    assert body["auto_ingested"] == ["https://exemplo.com/"]
    assert body["queued"] == []
    assert len(fake_qdrant.upserts) == 1


def test_run_confidence_baixa_enfileira(db_session, active_collection, tmp_path):
    html = '<html><body><p>Conteúdo ambíguo</p></body></html>'
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.3)
    app = _build_app(
        fake_qdrant, db_session, tmp_path, llm,
        paginas={"https://exemplo.com/": (200, "text/html", html)},
    )
    client = TestClient(app)

    response = client.post("/api/rag/crawler/run", json={"url": "https://exemplo.com/", "depth": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["queued"] == ["https://exemplo.com/"]
    assert fake_qdrant.upserts == []

    pendentes = client.get("/api/rag/crawler/pending").json()
    assert len(pendentes) == 1
    assert pendentes[0]["url"] == "https://exemplo.com/"
    assert pendentes[0]["domain_proposed"] == "vendas"


def test_run_usa_max_pages_default_quando_nao_informado(db_session, active_collection, tmp_path):
    html_com_link = (
        '<html><body><a href="/a">a</a><a href="/b">b</a><a href="/c">c</a></body></html>'
    )
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    paginas = {
        "https://exemplo.com/": (200, "text/html", html_com_link),
        "https://exemplo.com/a": (200, "text/html", "<html><body>a</body></html>"),
        "https://exemplo.com/b": (200, "text/html", "<html><body>b</body></html>"),
        "https://exemplo.com/c": (200, "text/html", "<html><body>c</body></html>"),
    }
    app = _build_app(fake_qdrant, db_session, tmp_path, llm, max_pages_default=2, paginas=paginas)
    client = TestClient(app)

    response = client.post("/api/rag/crawler/run", json={"url": "https://exemplo.com/", "depth": 1})

    assert response.json()["pages_visited"] == 2


def test_run_sem_collection_ativa_retorna_503(db_session, tmp_path):
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    app = _build_app(fake_qdrant, db_session, tmp_path, llm)
    client = TestClient(app)

    response = client.post("/api/rag/crawler/run", json={"url": "https://exemplo.com/", "depth": 0})

    assert response.status_code == 503


def test_approve_pending_page_ingere_com_domain_escolhido(db_session, active_collection, tmp_path):
    from app.rag.crawler_pending import upsert_pending_page

    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    page = None

    async def _seed():
        nonlocal page
        page = await upsert_pending_page(
            db_session,
            url="https://exemplo.com/ambiguo",
            extracted_text="conteúdo ambíguo",
            domain_proposed="vendas",
            confidence=0.3,
        )

    import asyncio

    asyncio.run(_seed())
    app = _build_app(fake_qdrant, db_session, tmp_path, llm)
    client = TestClient(app)

    response = client.post(
        f"/api/rag/crawler/pending/{page.id}/approve", json={"domain": "suporte"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"url": "https://exemplo.com/ambiguo", "domain": "suporte", "chunks": 1}
    assert len(fake_qdrant.upserts) == 1
    assert client.get("/api/rag/crawler/pending").json() == []


def test_approve_pending_page_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    app = _build_app(fake_qdrant, db_session, tmp_path, llm)
    client = TestClient(app)

    response = client.post(
        "/api/rag/crawler/pending/00000000-0000-0000-0000-000000000000/approve",
        json={"domain": "vendas"},
    )

    assert response.status_code == 404


def test_reject_pending_page_remove_sem_ingerir(db_session, active_collection, tmp_path):
    from app.rag.crawler_pending import upsert_pending_page

    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    page = None

    async def _seed():
        nonlocal page
        page = await upsert_pending_page(
            db_session,
            url="https://exemplo.com/ambiguo",
            extracted_text="conteúdo ambíguo",
            domain_proposed="vendas",
            confidence=0.3,
        )

    import asyncio

    asyncio.run(_seed())
    app = _build_app(fake_qdrant, db_session, tmp_path, llm)
    client = TestClient(app)

    response = client.post(f"/api/rag/crawler/pending/{page.id}/reject")

    assert response.status_code == 204
    assert fake_qdrant.upserts == []
    assert client.get("/api/rag/crawler/pending").json() == []


def test_reject_pending_page_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    app = _build_app(fake_qdrant, db_session, tmp_path, llm)
    client = TestClient(app)

    response = client.post(
        "/api/rag/crawler/pending/00000000-0000-0000-0000-000000000000/reject"
    )

    assert response.status_code == 404
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/pytest tests/test_crawler_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.crawler'`

- [ ] **Step 3: Implementar `app/api/crawler.py`**

```python
"""Endpoints HTTP do crawler de páginas do RAG (R4, Fase 2) — dispara um
crawl a partir de uma URL semente, e gerencia a fila de revisão de páginas
cuja classificação de domínio ficou abaixo do limiar de confiança. Ver
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.

# MVP: sem autenticação (mesma decisão do restante de `app.api.rag`) e
execução síncrona do `/run` — sem fila de background nem agendamento.
"""

import logging
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import (
    get_db_session,
    get_embedder_registry,
    get_qdrant_client,
    get_uploads_dir,
)
from app.db.models import CrawlerPendingPage
from app.models.crawler import (
    ApprovedPageResponse,
    ApprovePendingPageRequest,
    CrawlRunRequest,
    CrawlRunResponse,
    PendingPageResponse,
)
from app.rag.collections_registry import get_active_collection
from app.rag.crawler import crawl
from app.rag.crawler_classifier import classify_page
from app.rag.crawler_ingest import ingest_or_queue, replace_previous_ingestion
from app.rag.crawler_pending import delete_pending_page, get_pending_page, list_pending_pages
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag/crawler", tags=["crawler"])

_TEXT_SNIPPET_CHARS = 300

# Falhas ao classificar/ingerir uma página específica não abortam o resto do
# crawl (spec §5) — capturadas aqui e reportadas em `errors`.
_ERROS_POR_PAGINA = (RAGConnectionError, httpx.HTTPError, SQLAlchemyError)


def _to_pending_response(page: CrawlerPendingPage) -> PendingPageResponse:
    return PendingPageResponse(
        id=page.id,
        url=page.url,
        text_snippet=page.extracted_text[:_TEXT_SNIPPET_CHARS],
        domain_proposed=page.domain_proposed,
        confidence=page.confidence,
        created_at=page.created_at,
    )


@router.post("/run", response_model=CrawlRunResponse)
async def run_crawler(
    body: CrawlRunRequest,
    request: Request,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> CrawlRunResponse:
    collection = await get_active_collection(session)
    if collection is None:
        raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    max_pages = body.max_pages or request.app.state.crawler_max_pages_default
    confidence_threshold = request.app.state.crawler_confidence_threshold
    embedder = embedders.get(collection.embedding_model)

    result = await crawl(request.app.state.crawler_http_client, str(body.url), body.depth, max_pages)

    auto_ingested: list[str] = []
    queued: list[str] = []
    errors = list(result.errors)

    for page in result.pages:
        try:
            classification = await classify_page(request.app.state.external_client, page.text)
            outcome = await ingest_or_queue(
                session,
                qdrant,
                collection,
                embedder,
                uploads_dir,
                page.url,
                page.text,
                classification,
                confidence_threshold,
            )
        except _ERROS_POR_PAGINA as exc:
            logger.error(
                "crawler_pagina_indisponivel",
                extra={
                    "crawler": {"event": "crawler_pagina_indisponivel", "url": page.url, "erro": str(exc)}
                },
            )
            errors.append(page.url)
            continue

        if outcome == "ingested":
            auto_ingested.append(page.url)
        else:
            queued.append(page.url)

    return CrawlRunResponse(
        pages_visited=len(result.pages), auto_ingested=auto_ingested, queued=queued, errors=errors
    )


@router.get("/pending", response_model=list[PendingPageResponse])
async def get_pending(session: AsyncSession = Depends(get_db_session)) -> list[PendingPageResponse]:
    pages = await list_pending_pages(session)
    return [_to_pending_response(page) for page in pages]


@router.post("/pending/{page_id}/approve", response_model=ApprovedPageResponse)
async def approve_pending(
    page_id: UUID,
    body: ApprovePendingPageRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovedPageResponse:
    page = await get_pending_page(session, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Página pendente não encontrada.")

    collection = await get_active_collection(session)
    if collection is None:
        raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    embedder = embedders.get(collection.embedding_model)
    try:
        await replace_previous_ingestion(session, qdrant, collection, page.url)
        documento = await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename=page.url,
            content=page.extracted_text.encode("utf-8"),
            domain=body.domain,
            session=session,
            origin="crawler",
        )
    except RAGConnectionError as exc:
        logger.error(
            "crawler_approve_indisponivel",
            extra={"crawler": {"event": "crawler_approve_indisponivel", "url": page.url, "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail="Serviço de registro de documentos temporariamente indisponível, tente novamente.",
        ) from exc

    await delete_pending_page(session, page_id)
    return ApprovedPageResponse(url=page.url, domain=body.domain, chunks=documento.chunk_count)


@router.post("/pending/{page_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_pending(page_id: UUID, session: AsyncSession = Depends(get_db_session)) -> None:
    deleted = await delete_pending_page(session, page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Página pendente não encontrada.")
```

- [ ] **Step 4: Registrar o router e o cliente HTTP compartilhado em `app/main.py`**

Adicionar o import (junto aos outros de `app.api`):

```python
from app.api.crawler import router as crawler_router
```

Adicionar `import httpx` no grupo de imports de terceiros, junto a
`from fastapi import FastAPI` (ordem alfabética do `ruff`/`isort`: `fastapi`
antes de `httpx`):

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
```

(ruff reordena automaticamente em `ruff check --fix .`/`ruff format .` se a
ordem ficar diferente — não é preciso acertar manualmente byte a byte.)

Logo após `app.state.crawler_confidence_threshold = settings.crawler_confidence_threshold` (Task 7, Step 5):

```python
    # Cliente HTTP dedicado ao crawler (spec
    # docs/superpowers/specs/2026-09-19-crawler-paginas-design.md) — separado
    # de `external_client`/`local_client`, que são clientes de LLM, não de
    # fetch de páginas arbitrárias.
    app.state.crawler_http_client = httpx.AsyncClient()
```

E, junto aos demais `app.include_router(...)`:

```python
    app.include_router(crawler_router)
```

- [ ] **Step 5: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/pytest tests/test_crawler_api.py -v`
Expected: PASS (todos os testes)

- [ ] **Step 6: Rodar a suíte completa do backend**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS (nenhuma regressão nos módulos existentes)

- [ ] **Step 7: Commit**

```bash
git add backend/src/app/api/crawler.py backend/src/app/main.py backend/tests/test_crawler_api.py
git commit -m "feat(rag): endpoints do crawler de páginas — run/pending/approve/reject (R4, Fase 2)"
```

---

### Task 10: Frontend — tipos do contrato do crawler

**Files:**
- Create: `frontend/lib/types/crawler.ts`
- Modify: `frontend/lib/types/runtimeSettings.ts`

**Interfaces:**
- Consumes: `RagDomain` (`frontend/lib/types/rag.ts:9`).
- Produces: `CrawlRunPayload`, `CrawlRunResponse`, `PendingPage`, `ApprovePendingPagePayload`, `ApprovedPageResponse` (`frontend/lib/types/crawler.ts`); `RuntimeSettings.crawler_max_pages_default: number`, `RuntimeSettings.crawler_confidence_threshold: number`.

Este módulo é só tipos (sem lógica) — sem teste próprio; a tipagem é validada pelo `tsc`/build e pelos testes dos componentes (Tasks 12-14).

- [ ] **Step 1: Criar `frontend/lib/types/crawler.ts`**

```ts
/**
 * Tipos do contrato dos endpoints do crawler de páginas do RAG (ver
 * `backend/src/app/models/crawler.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

import type { RagDomain } from "@/lib/types/rag";

/** Corpo de `POST /api/rag/crawler/run`. */
export interface CrawlRunPayload {
  url: string;
  depth: number;
  max_pages?: number;
}

/** Resposta de `POST /api/rag/crawler/run`. */
export interface CrawlRunResponse {
  pages_visited: number;
  auto_ingested: string[];
  queued: string[];
  errors: string[];
}

/** Um item de `GET /api/rag/crawler/pending`. */
export interface PendingPage {
  id: string;
  url: string;
  text_snippet: string;
  domain_proposed: RagDomain;
  confidence: number;
  created_at: string;
}

/** Corpo de `POST /api/rag/crawler/pending/{id}/approve`. */
export interface ApprovePendingPagePayload {
  domain: RagDomain;
}

/** Resposta de `POST /api/rag/crawler/pending/{id}/approve`. */
export interface ApprovedPageResponse {
  url: string;
  domain: RagDomain;
  chunks: number;
}
```

- [ ] **Step 2: Atualizar `frontend/lib/types/runtimeSettings.ts`**

```ts
/**
 * Tipos do contrato de `GET`/`PUT /api/admin/runtime-settings` (ver
 * `backend/src/app/models/runtime_settings.py`) — parâmetros de execução
 * ajustáveis em runtime (temperatura do Ollama, timeouts, fallback de
 * domínio do RAG, teto default/limiar de confiança do crawler), só em
 * memória, resetam a cada restart do backend.
 */

export interface RuntimeSettings {
  local_llm_temperature: number | null;
  local_llm_timeout_s: number;
  external_llm_timeout_s: number;
  rag_search_domain_fallback: boolean;
  crawler_max_pages_default: number;
  crawler_confidence_threshold: number;
}

/** Corpo de `PUT /api/admin/runtime-settings` — atualização parcial, só os
 * campos presentes são alterados (`local_llm_temperature: null` reseta
 * explicitamente para o default do próprio modelo). */
export type RuntimeSettingsUpdate = Partial<RuntimeSettings>;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types/crawler.ts frontend/lib/types/runtimeSettings.ts
git commit -m "feat(frontend): tipos do contrato do crawler de páginas (R4, Fase 2)"
```

---

### Task 11: Frontend — cliente de API do crawler

**Files:**
- Create: `frontend/lib/api/crawler.ts`

**Interfaces:**
- Consumes: `extrairDetalheDeErro` (`frontend/lib/api/errors.ts:49`), tipos da Task 10.
- Produces: `CrawlerApiError`, `runCrawler(payload: CrawlRunPayload): Promise<CrawlRunResponse>`, `listPendingPages(): Promise<PendingPage[]>`, `approvePendingPage(id: string, payload: ApprovePendingPagePayload): Promise<ApprovedPageResponse>`, `rejectPendingPage(id: string): Promise<void>`.

Sem teste próprio — exercitado pelos testes dos componentes (Tasks 12-13), mesmo padrão de `lib/api/rag.ts`/`lib/api/runtimeSettings.ts` neste projeto (que também não têm arquivo de teste dedicado).

- [ ] **Step 1: Criar `frontend/lib/api/crawler.ts`**

```ts
import type {
  ApprovedPageResponse,
  ApprovePendingPagePayload,
  CrawlRunPayload,
  CrawlRunResponse,
  PendingPage,
} from "@/lib/types/crawler";
import { extrairDetalheDeErro } from "@/lib/api/errors";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com os endpoints do crawler (rede ou HTTP não-2xx). */
export class CrawlerApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "CrawlerApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  const message =
    detail ??
    (response.status === 503
      ? "Serviço de RAG temporariamente indisponível. Tente novamente."
      : mensagemPadrao);
  throw new CrawlerApiError(message, response.status);
}

/** Dispara um crawl a partir de uma URL semente via `POST /api/rag/crawler/run`. */
export async function runCrawler(payload: CrawlRunPayload): Promise<CrawlRunResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível rodar o crawler. Tente novamente.");
  }

  return (await response.json()) as CrawlRunResponse;
}

/** Lista a fila de revisão via `GET /api/rag/crawler/pending`. */
export async function listPendingPages(): Promise<PendingPage[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending`);
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new CrawlerApiError(
      "Não foi possível carregar a fila de revisão. Tente novamente.",
      response.status,
    );
  }

  return (await response.json()) as PendingPage[];
}

/** Aprova uma página pendente via `POST /api/rag/crawler/pending/{id}/approve`. */
export async function approvePendingPage(
  id: string,
  payload: ApprovePendingPagePayload,
): Promise<ApprovedPageResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível aprovar a página. Tente novamente.");
  }

  return (await response.json()) as ApprovedPageResponse;
}

/** Rejeita uma página pendente via `POST /api/rag/crawler/pending/{id}/reject`. */
export async function rejectPendingPage(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/reject`, { method: "POST" });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 404
        ? "Página pendente não encontrada (talvez já tenha sido revisada)."
        : "Não foi possível rejeitar a página. Tente novamente.";
    throw new CrawlerApiError(message, response.status);
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/api/crawler.ts
git commit -m "feat(frontend): cliente de API do crawler de páginas (R4, Fase 2)"
```

---

### Task 12: Frontend — `CrawlerPanel` (form de disparo)

**Files:**
- Create: `frontend/components/admin/CrawlerPanel.tsx`
- Test: `frontend/tests/components/CrawlerPanel.test.tsx`

**Interfaces:**
- Consumes: `runCrawler`, `CrawlerApiError` (Task 11), `getRuntimeSettings` (`frontend/lib/api/runtimeSettings.ts:23`).
- Produces: `CrawlerPanel({ onFinished }: { onFinished: () => void })`.

- [ ] **Step 1: Escrever o teste (falhando)**

Criar `frontend/tests/components/CrawlerPanel.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { CrawlerApiError } from "@/lib/api/crawler";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, runCrawler: vi.fn() };
});
vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/runtimeSettings")>("@/lib/api/runtimeSettings");
  return { ...actual, getRuntimeSettings: vi.fn() };
});

import { runCrawler } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";

const mockedRunCrawler = vi.mocked(runCrawler);
const mockedGetRuntimeSettings = vi.mocked(getRuntimeSettings);

describe("CrawlerPanel", () => {
  beforeEach(() => {
    mockedRunCrawler.mockReset();
    mockedGetRuntimeSettings.mockReset();
    mockedGetRuntimeSettings.mockResolvedValue({
      local_llm_temperature: null,
      local_llm_timeout_s: 30,
      external_llm_timeout_s: 30,
      rag_search_domain_fallback: false,
      crawler_max_pages_default: 20,
      crawler_confidence_threshold: 0.7,
    });
  });

  it("dispara o crawl com a URL/profundidade informadas e mostra o resumo", async () => {
    const user = userEvent.setup();
    mockedRunCrawler.mockResolvedValueOnce({
      pages_visited: 3,
      auto_ingested: ["https://exemplo.com/", "https://exemplo.com/a"],
      queued: ["https://exemplo.com/b"],
      errors: [],
    });
    const onFinished = vi.fn();

    render(<CrawlerPanel onFinished={onFinished} />);

    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText(/3 página\(s\) visitada\(s\)/)).toBeInTheDocument();
    expect(mockedRunCrawler).toHaveBeenCalledWith(
      expect.objectContaining({ url: "https://exemplo.com", depth: 1 }),
    );
    await waitFor(() => expect(onFinished).toHaveBeenCalled());
  });

  it("mostra o erro quando o crawler falha", async () => {
    const user = userEvent.setup();
    mockedRunCrawler.mockRejectedValueOnce(new CrawlerApiError("Serviço indisponível."));

    render(<CrawlerPanel onFinished={vi.fn()} />);

    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText("Serviço indisponível.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npm test -- CrawlerPanel`
Expected: FAIL — módulo `@/components/admin/CrawlerPanel` não existe.

- [ ] **Step 3: Implementar `frontend/components/admin/CrawlerPanel.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";

import { CrawlerApiError, runCrawler } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";
import type { CrawlRunResponse } from "@/lib/types/crawler";

export function CrawlerPanel({ onFinished }: { onFinished: () => void }) {
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState(1);
  const [maxPages, setMaxPages] = useState<number | "">("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<CrawlRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Só usado pra pré-preencher `maxPages` — falha ao carregar não impede o
    // form de funcionar (o backend usa seu próprio default se `max_pages`
    // não for enviado).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    getRuntimeSettings()
      .then((settings) => setMaxPages(settings.crawler_max_pages_default))
      .catch(() => {});
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!url || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await runCrawler({
        url,
        depth,
        max_pages: maxPages === "" ? undefined : maxPages,
      });
      setResult(response);
      onFinished();
    } catch (err) {
      setError(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao rodar o crawler.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Navega a partir de uma URL semente (site próprio ou externo), seguindo links internos até a
        profundidade informada, e classifica cada página por domínio.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
        <div>
          <label htmlFor="crawler-url" className="block text-sm font-medium text-gray-900">
            URL semente
          </label>
          <input
            id="crawler-url"
            type="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://exemplo.com"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="crawler-depth" className="block text-sm font-medium text-gray-900">
              Profundidade
            </label>
            <input
              id="crawler-depth"
              type="number"
              min={0}
              required
              value={depth}
              onChange={(event) => setDepth(Number(event.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
          <div>
            <label htmlFor="crawler-max-pages" className="block text-sm font-medium text-gray-900">
              Máximo de páginas
            </label>
            <input
              id="crawler-max-pages"
              type="number"
              min={1}
              value={maxPages}
              onChange={(event) =>
                setMaxPages(event.target.value === "" ? "" : Number(event.target.value))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!url || isSubmitting}
          className="rounded-md bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {isSubmitting ? "Rodando..." : "Rodar crawler"}
        </button>
      </form>

      {result && (
        <p className="mt-6 rounded-md bg-green-50 px-4 py-3 text-green-800">
          {result.pages_visited} página(s) visitada(s) — {result.auto_ingested.length} ingerida(s)
          diretamente, {result.queued.length} na fila de revisão
          {result.errors.length > 0 ? `, ${result.errors.length} com erro` : ""}.
        </p>
      )}
      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npm test -- CrawlerPanel`
Expected: PASS (os dois testes)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/CrawlerPanel.tsx frontend/tests/components/CrawlerPanel.test.tsx
git commit -m "feat(frontend): form de disparo do crawler de páginas (R4, Fase 2)"
```

---

### Task 13: Frontend — `CrawlerReviewQueue` (fila de revisão)

**Files:**
- Create: `frontend/components/admin/CrawlerReviewQueue.tsx`
- Test: `frontend/tests/components/CrawlerReviewQueue.test.tsx`

**Interfaces:**
- Consumes: `listPendingPages`, `approvePendingPage`, `rejectPendingPage`, `CrawlerApiError` (Task 11), `useToast`/`ToastStack` (`frontend/components/ui/Toast.tsx`).
- Produces: `CrawlerReviewQueue({ reloadKey }: { reloadKey: number })`.

- [ ] **Step 1: Escrever o teste (falhando)**

Criar `frontend/tests/components/CrawlerReviewQueue.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
import type { PendingPage } from "@/lib/types/crawler";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, listPendingPages: vi.fn(), approvePendingPage: vi.fn(), rejectPendingPage: vi.fn() };
});

import { approvePendingPage, listPendingPages, rejectPendingPage } from "@/lib/api/crawler";

const mockedList = vi.mocked(listPendingPages);
const mockedApprove = vi.mocked(approvePendingPage);
const mockedReject = vi.mocked(rejectPendingPage);

const PAGINA: PendingPage = {
  id: "pagina-1",
  url: "https://exemplo.com/ambiguo",
  text_snippet: "trecho do conteúdo",
  domain_proposed: "vendas",
  confidence: 0.42,
  created_at: new Date().toISOString(),
};

describe("CrawlerReviewQueue", () => {
  beforeEach(() => {
    mockedList.mockReset();
    mockedApprove.mockReset();
    mockedReject.mockReset();
  });

  it("mostra a mensagem de fila vazia quando não há páginas pendentes", async () => {
    mockedList.mockResolvedValueOnce([]);

    render(<CrawlerReviewQueue reloadKey={0} />);

    expect(await screen.findByText("Nenhuma página pendente de revisão.")).toBeInTheDocument();
  });

  it("aprova a página com o domain selecionado e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedApprove.mockResolvedValueOnce({ url: PAGINA.url, domain: "suporte", chunks: 1 });

    render(<CrawlerReviewQueue reloadKey={0} />);

    await screen.findByText(PAGINA.url);
    await user.selectOptions(screen.getByRole("combobox"), "suporte");
    await user.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(mockedApprove).toHaveBeenCalledWith(PAGINA.id, { domain: "suporte" });
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });

  it("rejeita a página e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedReject.mockResolvedValueOnce(undefined);

    render(<CrawlerReviewQueue reloadKey={0} />);

    await screen.findByText(PAGINA.url);
    await user.click(screen.getByRole("button", { name: "Rejeitar" }));

    expect(mockedReject).toHaveBeenCalledWith(PAGINA.id);
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npm test -- CrawlerReviewQueue`
Expected: FAIL — módulo `@/components/admin/CrawlerReviewQueue` não existe.

- [ ] **Step 3: Implementar `frontend/components/admin/CrawlerReviewQueue.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";

import { ToastStack, useToast } from "@/components/ui/Toast";
import { CrawlerApiError, approvePendingPage, listPendingPages, rejectPendingPage } from "@/lib/api/crawler";
import type { PendingPage } from "@/lib/types/crawler";
import type { RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

export function CrawlerReviewQueue({ reloadKey }: { reloadKey: number }) {
  const [pages, setPages] = useState<PendingPage[] | null>(null);
  const [selectedDomain, setSelectedDomain] = useState<Record<string, RagDomain>>({});
  const [processingId, setProcessingId] = useState<string | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregar = useCallback(async () => {
    try {
      const carregadas = await listPendingPages();
      setPages(carregadas);
      setSelectedDomain((atual) => {
        const proximo = { ...atual };
        for (const page of carregadas) {
          proximo[page.id] = proximo[page.id] ?? page.domain_proposed;
        }
        return proximo;
      });
    } catch (err) {
      showToast(
        err instanceof CrawlerApiError ? err.message : "Erro inesperado ao carregar a fila de revisão.",
        "error",
      );
      setPages([]);
    }
  }, [showToast]);

  useEffect(() => {
    // `carregar` só chama `setPages`/`showToast` depois do `await`
    // (assíncrono, não durante a execução síncrona do efeito) — falso
    // positivo conhecido de `react-hooks/set-state-in-effect`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregar();
  }, [carregar, reloadKey]);

  async function handleApprove(page: PendingPage) {
    setProcessingId(page.id);
    try {
      await approvePendingPage(page.id, { domain: selectedDomain[page.id] ?? page.domain_proposed });
      showToast(`"${page.url}" aprovada e ingerida.`, "success");
      setPages((atual) => atual?.filter((p) => p.id !== page.id) ?? null);
    } catch (err) {
      showToast(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao aprovar.", "error");
    } finally {
      setProcessingId(null);
    }
  }

  async function handleReject(page: PendingPage) {
    setProcessingId(page.id);
    try {
      await rejectPendingPage(page.id);
      showToast(`"${page.url}" rejeitada.`, "success");
      setPages((atual) => atual?.filter((p) => p.id !== page.id) ?? null);
    } catch (err) {
      showToast(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao rejeitar.", "error");
    } finally {
      setProcessingId(null);
    }
  }

  if (pages === null) {
    return <p className="text-sm text-gray-600">Carregando...</p>;
  }

  if (pages.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma página pendente de revisão.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
      <table className="w-full min-w-[700px] text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
            <th className="py-3 px-4">URL</th>
            <th className="py-3 px-4">Trecho</th>
            <th className="py-3 px-4">Domínio</th>
            <th className="py-3 px-4">Confiança</th>
            <th className="py-3 px-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {pages.map((page) => (
            <tr key={page.id} className="transition-colors hover:bg-slate-50/60">
              <td className="py-3.5 px-4 font-semibold text-slate-900 break-all">{page.url}</td>
              <td className="py-3.5 px-4 text-slate-600 text-xs">{page.text_snippet}</td>
              <td className="py-3.5 px-4">
                <select
                  value={selectedDomain[page.id] ?? page.domain_proposed}
                  onChange={(event) =>
                    setSelectedDomain((atual) => ({
                      ...atual,
                      [page.id]: event.target.value as RagDomain,
                    }))
                  }
                  className="rounded-md border border-gray-300 px-2 py-1 text-sm text-gray-900"
                >
                  {DOMAIN_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </td>
              <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">
                {page.confidence.toFixed(2)}
              </td>
              <td className="py-3.5 px-4 text-right whitespace-nowrap">
                <button
                  type="button"
                  disabled={processingId === page.id}
                  onClick={() => handleApprove(page)}
                  className="mr-2 inline-flex items-center gap-1 rounded-lg border border-green-200/80 bg-green-50/50 px-2.5 py-1 text-xs font-semibold text-green-700 shadow-2xs transition-colors hover:bg-green-100/80 hover:text-green-800 disabled:opacity-50"
                >
                  Aprovar
                </button>
                <button
                  type="button"
                  disabled={processingId === page.id}
                  onClick={() => handleReject(page)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-200/80 bg-red-50/50 px-2.5 py-1 text-xs font-semibold text-red-600 shadow-2xs transition-colors hover:bg-red-100/80 hover:text-red-700 disabled:opacity-50"
                >
                  Rejeitar
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npm test -- CrawlerReviewQueue`
Expected: PASS (os três testes)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/CrawlerReviewQueue.tsx frontend/tests/components/CrawlerReviewQueue.test.tsx
git commit -m "feat(frontend): fila de revisão do crawler de páginas (R4, Fase 2)"
```

---

### Task 14: Frontend — nova aba "Crawler" em `/admin/ingestao`

**Files:**
- Modify: `frontend/app/admin/ingestao/page.tsx`

**Interfaces:**
- Consumes: `CrawlerPanel` (Task 12), `CrawlerReviewQueue` (Task 13).

- [ ] **Step 1: Adicionar os imports**

Em `frontend/app/admin/ingestao/page.tsx`, junto aos demais imports de `@/components/admin/*`:

```tsx
import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
```

- [ ] **Step 2: Adicionar o componente da aba**

Logo antes de `export default function IngestaoDocumentosPage()`:

```tsx
function AbaCrawler() {
  const [reloadKey, setReloadKey] = useState(0);
  return (
    <div className="space-y-6">
      <CrawlerPanel onFinished={() => setReloadKey((key) => key + 1)} />
      <CrawlerReviewQueue reloadKey={reloadKey} />
    </div>
  );
}
```

- [ ] **Step 3: Registrar a aba na navegação**

Em `TabsList`, depois de `<TabsTrigger value="playground">Playground</TabsTrigger>`:

```tsx
          <TabsTrigger value="crawler">Crawler</TabsTrigger>
```

Dentro do container de conteúdo, depois de `<TabsContent value="playground">...</TabsContent>`:

```tsx
          <TabsContent value="crawler">
            <AbaCrawler />
          </TabsContent>
```

- [ ] **Step 4: Rodar a suíte de testes do frontend (regressão)**

Run: `cd frontend && npm test`
Expected: PASS (todos os testes, incluindo `IngestaoDocumentosPage.test.tsx` sem regressão)

- [ ] **Step 5: Rodar o build/typecheck**

Run: `cd frontend && npm run build`
Expected: build sem erro de tipo.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/admin/ingestao/page.tsx
git commit -m "feat(frontend): integra o crawler de páginas em /admin/ingestao (R4, Fase 2)"
```

---

### Task 15: Verificação final, lint e roadmap

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Rodar lint/format do backend**

Run: `cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .`
Expected: sem erros. Se `ruff format` sinalizar diffs, rodar `.venv/bin/ruff format .` e revisar antes de commitar.

- [ ] **Step 2: Rodar a suíte completa do backend**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS (todos os módulos, sem regressão).

- [ ] **Step 3: Rodar lint e testes do frontend**

Run: `cd frontend && npm run lint && npm test`
Expected: sem erros, todos os testes passando.

- [ ] **Step 4: Testar manualmente o fluxo ponta a ponta**

Com o backend (`uvicorn app.main:app --app-dir src --host 0.0.0.0 --port 8000`), o Postgres/Qdrant do `docker-compose.yml` e o frontend (`npm run dev`) no ar: abrir `/admin/ingestao`, aba "Crawler", rodar um crawl contra um site real com `depth=1` e conferir que (a) o resumo aparece, (b) páginas de alta confiança somem da lista mas aparecem em "Documentos ingeridos", (c) páginas de baixa confiança aparecem na fila de revisão e podem ser aprovadas (com domain trocado) ou rejeitadas.

- [ ] **Step 5: Marcar o item concluído em `docs/ROADMAP.md`**

Em `backend/../docs/ROADMAP.md`, trocar a caixa do item do crawler (linha adicionada na correção de escopo desta mesma entrega):

```markdown
- [x] Implementar crawler disparado manualmente pelo admin a partir de uma
      URL semente (interna ou externa), com profundidade e teto de páginas
      parametrizáveis por execução, sem agendamento (`# MVP: escopo
      restrito`) — ver
      `docs/superpowers/specs/2026-09-19-crawler-paginas-design.md`
```

- [ ] **Step 6: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs: marca crawler de páginas como concluído no roadmap (R4, Fase 2)"
```
