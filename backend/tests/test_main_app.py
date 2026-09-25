"""Smoke test de `create_app()` — garante que a montagem de app.state e o
registro de routers não quebram (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1)."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.sales_catalog import SalesCatalogClient
from app.router.scheduling import SchedulingConfig


def test_create_app_monta_o_estado_do_rag_corretamente():
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
