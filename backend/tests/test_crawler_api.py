import json

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

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
    html = "<html><body><p>Conteúdo de vendas</p></body></html>"
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    app = _build_app(
        fake_qdrant,
        db_session,
        tmp_path,
        llm,
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
    html = "<html><body><p>Conteúdo ambíguo</p></body></html>"
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.3)
    app = _build_app(
        fake_qdrant,
        db_session,
        tmp_path,
        llm,
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


class _PoisonedAfterFirstCommitFailureSession:
    """Encapsula uma `AsyncSession` real: o primeiro `commit()` levanta
    `SQLAlchemyError` (simulando um hiccup transitório de Postgres) e, a
    partir daí, simula o estado de pending-rollback real do SQLAlchemy —
    qualquer operação seguinte (`execute`, `commit`) também levanta
    `SQLAlchemyError`, até que `rollback()` seja chamado. Usada para cobrir
    o achado #2 da revisão final: sem `session.rollback()` no `except` de
    `run_crawler`, uma falha de commit na página N convertia silenciosamente
    todas as páginas N+1..fim do mesmo crawl em "erro" também."""

    def __init__(self, session) -> None:
        self._session = session
        self._poisoned = False
        self._commits = 0

    def __getattr__(self, name):
        return getattr(self._session, name)

    async def commit(self) -> None:
        if self._poisoned:
            raise SQLAlchemyError("sessão em estado de rollback pendente (simulado)")
        self._commits += 1
        if self._commits == 1:
            self._poisoned = True
            raise SQLAlchemyError("falha simulada de commit na primeira página")
        await self._session.commit()

    async def execute(self, *args, **kwargs):
        if self._poisoned:
            raise SQLAlchemyError("sessão em estado de rollback pendente (simulado)")
        return await self._session.execute(*args, **kwargs)

    async def rollback(self) -> None:
        self._poisoned = False
        await self._session.rollback()


def test_run_com_falha_de_commit_em_uma_pagina_nao_contamina_as_seguintes(
    db_session, active_collection, tmp_path
):
    """Achado #2 da revisão final: uma falha de `SQLAlchemyError` na página 1
    não deve fazer a página 2 (mesmo crawl) também "falhar" só por causa do
    estado pendente da sessão — o handler precisa dar `rollback()`."""
    html_indice = '<html><body><a href="/outra">outra</a></body></html>'
    paginas = {
        "https://exemplo.com/": (200, "text/html", html_indice),
        "https://exemplo.com/outra": (200, "text/html", "<html><body>outra página</body></html>"),
    }
    fake_qdrant = _FakeQdrantRAGClient()
    llm = _FakeLLMClient(domain="vendas", confidence=0.9)
    session_com_falha = _PoisonedAfterFirstCommitFailureSession(db_session)
    app = _build_app(fake_qdrant, session_com_falha, tmp_path, llm, paginas=paginas)
    client = TestClient(app)

    response = client.post("/api/rag/crawler/run", json={"url": "https://exemplo.com/", "depth": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["pages_visited"] == 2
    assert body["errors"] == ["https://exemplo.com/"]
    assert body["auto_ingested"] == ["https://exemplo.com/outra"]


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

    response = client.post("/api/rag/crawler/pending/00000000-0000-0000-0000-000000000000/reject")

    assert response.status_code == 404
