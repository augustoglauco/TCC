"""Smoke test de `create_app()` — garante que a montagem de app.state e o
registro de routers não quebram (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import _apply_runtime_settings, create_app
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.sales_catalog import SalesCatalogClient
from app.router.scheduling import SchedulingConfig


def test_apply_runtime_settings_coerce_e_agent_runtime():
    """Cobre as chaves que antes tinham tratamento especial fora do loop:
    local_llm_keep_alive (coerce str), local_llm_warmup_on_startup (coerce bool),
    estoque_agent_mode e estoque_agent_llm (target agent_runtime)."""
    from app.agents.runtime import runtime as agent_runtime

    class _FakeLocal:
        keep_alive = "-1"
        warmup = True

    class _FakeQdrant:
        search_domain_fallback = False

    app = FastAPI()
    app.state.local_client = _FakeLocal()
    app.state.external_client = None
    app.state.qdrant_client = _FakeQdrant()
    app.state.local_llm_warmup_on_startup = True

    _apply_runtime_settings(
        app,
        {
            "local_llm_keep_alive": 30,  # int → deve virar str "30"
            "local_llm_warmup_on_startup": 0,  # falsy int → deve virar bool False
            "rag_search_domain_fallback": 1,  # truthy int → deve virar bool True
            "estoque_agent_mode": "llm",
            "estoque_agent_llm": "external",
        },
    )

    assert app.state.local_client.keep_alive == "30"
    assert app.state.local_llm_warmup_on_startup is False
    assert app.state.qdrant_client.search_domain_fallback is True
    assert agent_runtime.estoque_modo == "llm"
    assert agent_runtime.estoque_llm == "external"

    app = create_app()

    assert isinstance(app.state.qdrant_client, QdrantRAGClient)
    assert isinstance(app.state.embedder_registry, EmbedderRegistry)
    assert isinstance(app.state.rag_client, ActiveCollectionRagClient)
    assert app.state.rag_uploads_dir is not None


def test_rotas_de_collections_e_playground_estao_registradas():
    app = create_app()
    client = TestClient(app)
    # NOTA: nesta versão do FastAPI (0.141.x), `app.routes` não expõe mais as
    # rotas de routers incluídos via `.path` diretamente (agora aparecem como
    # `_IncludedRouter`, resolvidas só em runtime) — por isso a checagem usa
    # o schema OpenAPI, que é a forma estável de listar todos os paths
    # registrados independentemente da representação interna de roteamento.
    caminhos = set(app.openapi()["paths"].keys())

    assert "/api/rag/collections" in caminhos
    assert "/api/rag/playground/search" in caminhos
    del client  # só para garantir que a app sobe sem erro de import circular


def test_create_app_inicializa_o_progress_store_de_pull_de_modelos():
    app = create_app()

    assert app.state.model_pull_progress == {}


def test_rota_de_local_models_esta_registrada():
    app = create_app()
    caminhos = set(app.openapi()["paths"].keys())

    assert "/api/admin/local-models" in caminhos


def test_rotas_do_crawler_estao_registradas_e_o_estado_correspondente_tambem():
    """Achado #6 da revisão final: a Task 9 registrou `crawler_router` e o
    `app.state` que ele depende (`crawler_http_client`,
    `crawler_max_pages_default`, `crawler_confidence_threshold`) em
    `create_app()`, mas nenhum teste exercitava a app real — os 255 testes
    existentes montam `FastAPI()` "nuas" com dependency overrides, sem nunca
    passar por `create_app()`. Sem esta checagem, remover essa fiação por
    engano não quebraria nenhum teste."""
    app = create_app()
    caminhos = set(app.openapi()["paths"].keys())

    assert "/api/rag/crawler/run/stream" in caminhos
    assert "/api/rag/crawler/pending" in caminhos
    assert "/api/rag/crawler/pending/{page_id}/approve" in caminhos
    assert "/api/rag/crawler/pending/{page_id}/reject" in caminhos

    assert app.state.crawler_http_client is not None
    assert isinstance(app.state.crawler_max_pages_default, int)
    assert isinstance(app.state.crawler_confidence_threshold, float)


def test_create_app_monta_o_cliente_de_calendario_e_config_de_agendamento():
    app = create_app()

    assert isinstance(app.state.calendar_client, GoogleCalendarMCPClient)
    assert isinstance(app.state.scheduling_config, SchedulingConfig)
    assert app.state.scheduling_config.timezone == "America/Sao_Paulo"


def test_create_app_monta_o_sales_catalog_client():
    app = create_app()
    assert isinstance(app.state.sales_catalog_client, SalesCatalogClient)


async def test_startup_load_settings_nao_engole_erros_de_programacao(monkeypatch):
    """_startup_load_settings deve deixar erros de programação (ex.: AttributeError
    de _apply_runtime_settings) propagarem — só erros de infra (SQLAlchemy/OSError)
    são tolerados no startup."""
    import pytest
    from sqlalchemy.exc import OperationalError

    from app.main import _startup_load_settings

    app = FastAPI()
    app.state.local_client = None
    app.state.external_client = None
    app.state.qdrant_client = None

    # Simula falha de infra (DB fora do ar) — deve ser tolerada
    class _FakeSessionFactory:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise OperationalError("conn", {}, Exception("db down"))

        async def __aexit__(self, *_):
            pass

    await _startup_load_settings(app, _FakeSessionFactory())  # não deve levantar

    # Simula erro de programação dentro de _apply_runtime_settings — deve propagar
    class _FakeSessionFactoryOk:
        def __call__(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            pass

        async def execute(self, *_):
            return self

        def scalars(self):
            return self

        def all(self):
            return []

    monkeypatch.setattr(
        "app.main._apply_runtime_settings",
        lambda *_: (_ for _ in ()).throw(ValueError("bug")),
    )
    with pytest.raises(ValueError, match="bug"):
        await _startup_load_settings(app, _FakeSessionFactoryOk())


async def test_lifespan_restaura_settings_e_dispara_warmup(monkeypatch):
    import asyncio

    from app.db.engine import create_db_engine, create_session_factory
    from app.db.models import Base
    from app.db.settings import set_app_setting

    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        await set_app_setting(session, "local_llm_keep_alive", "12h")
        await set_app_setting(session, "local_llm_temperature", 0.42)
        await set_app_setting(session, "local_llm_warmup_on_startup", True)

    app = create_app()
    app.state.db_sessionmaker = session_factory

    preload_called = []

    async def fake_preload():
        preload_called.append(True)
        return True

    monkeypatch.setattr(app.state.local_client, "preload", fake_preload)

    async with app.router.lifespan_context(app):
        # Aguarda pequenas tarefas de background serem despachadas no event loop
        await asyncio.sleep(0.05)
        assert app.state.local_client.keep_alive == "12h"
        assert app.state.local_client.temperature == 0.42
        assert len(preload_called) == 1

    await engine.dispose()
