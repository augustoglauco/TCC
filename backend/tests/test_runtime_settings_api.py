from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.runtime_settings import router as runtime_settings_router


class _FakeLocalClient:
    def __init__(self, temperature: float | None, timeout_s: float) -> None:
        self.temperature = temperature
        self.timeout_s = timeout_s


class _FakeExternalClient:
    def __init__(self, timeout_s: float) -> None:
        self.timeout_s = timeout_s


class _FakeQdrantClient:
    def __init__(self, search_domain_fallback: bool) -> None:
        self.search_domain_fallback = search_domain_fallback


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


def test_put_atualiza_so_os_campos_enviados():
    app, local_client, external_client, qdrant_client = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"local_llm_temperature": 0.2})

    assert response.status_code == 200
    assert response.json()["local_llm_temperature"] == 0.2
    assert local_client.temperature == 0.2
    # Campos não enviados continuam com o valor original.
    assert local_client.timeout_s == 30.0
    assert external_client.timeout_s == 30.0
    assert qdrant_client.search_domain_fallback is False


def test_put_com_temperatura_null_explicito_reseta_para_default_do_modelo():
    app, local_client, *_ = _build_default_app()
    local_client.temperature = 0.5
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"local_llm_temperature": None})

    assert response.status_code == 200
    assert response.json()["local_llm_temperature"] is None
    assert local_client.temperature is None


def test_put_atualiza_todos_os_campos_de_uma_vez():
    app, local_client, external_client, qdrant_client = _build_default_app()
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={
            "local_llm_temperature": 0.0,
            "local_llm_timeout_s": 60.0,
            "external_llm_timeout_s": 45.0,
            "rag_search_domain_fallback": True,
        },
    )

    assert response.status_code == 200
    assert local_client.temperature == 0.0
    assert local_client.timeout_s == 60.0
    assert external_client.timeout_s == 45.0
    assert qdrant_client.search_domain_fallback is True


def test_put_temperatura_fora_do_intervalo_e_422():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"local_llm_temperature": 5.0})

    assert response.status_code == 422


def test_put_timeout_zero_ou_negativo_e_422():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put("/api/admin/runtime-settings", json={"local_llm_timeout_s": 0.0})

    assert response.status_code == 422


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
