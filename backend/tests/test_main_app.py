"""Smoke test de `create_app()` — garante que a montagem de app.state e o
registro de routers não quebram (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1)."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


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
