import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.model_catalog import router as model_catalog_router
from app.api.rag_dependencies import get_db_session


def _build_app(db_session, ollama_client=None, http_client=None) -> FastAPI:
    from app.api import model_catalog as mod

    app = FastAPI()
    app.include_router(model_catalog_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[mod.get_ollama_client] = lambda: ollama_client
    app.dependency_overrides[mod.get_model_catalog_http_client] = lambda: http_client
    return app


def _http_client_openrouter_ok() -> httpx.AsyncClient:
    payload = [{"id": "openai/gpt-4o-mini", "context_length": 128000, "architecture": {}}]

    def handler(request):
        return httpx.Response(200, json={"data": payload})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_get_characteristics_200_quando_encontrado(db_session):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=_http_client_openrouter_ok())
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "openrouter", "tag": "openai/gpt-4o-mini"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tag"] == "openai/gpt-4o-mini"
    assert body["context_length"] == 128000


def test_get_characteristics_404_quando_nao_encontrado(db_session):
    def handler(request):
        return httpx.Response(200, json={"data": []})

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "openrouter", "tag": "nao/existe"},
    )

    assert response.status_code == 404


def test_get_characteristics_source_invalido_422(db_session):
    app = _build_app(db_session)
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "invalido", "tag": "x"},
    )

    assert response.status_code == 422


def test_refresh_characteristics_forca_nova_busca(db_session):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=_http_client_openrouter_ok())
    client = TestClient(app)

    response = client.post(
        "/api/admin/model-catalog/characteristics/refresh",
        json={"source": "openrouter", "tag": "openai/gpt-4o-mini"},
    )

    assert response.status_code == 200
    assert response.json()["context_length"] == 128000
