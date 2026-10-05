from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag_dependencies import get_db_session
from app.api.runtime_settings import router as runtime_settings_router
from app.db.models import Cliente
from app.models.runtime_settings import (
    DEFAULT_INTENT_ROUTER_PROVIDER,
    DEFAULT_TONE_MONITOR_PROVIDER,
    IntentRouterProvider,
)


class _FakeLocalClient:
    def __init__(
        self,
        temperature: float | None = None,
        timeout_s: float = 30.0,
        num_ctx: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
        seed: int | None = None,
        keep_alive: str = "-1",
    ) -> None:
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.num_ctx = num_ctx
        self.top_p = top_p
        self.top_k = top_k
        self.repeat_penalty = repeat_penalty
        self.seed = seed
        self.keep_alive = keep_alive
        self.preloaded = False
        self.unloaded = False
        self.loaded_status: dict | None = None

    async def preload(self) -> bool:
        self.preloaded = True
        self.loaded_status = {"name": "test-model", "size_vram": 8589934592}
        return True

    async def unload(self) -> bool:
        self.unloaded = True
        self.loaded_status = None
        return True

    async def get_loaded_status(self) -> dict | None:
        return self.loaded_status


class _FakeExternalClient:
    def __init__(
        self, timeout_s: float, vision_model: str = "", model: str = "openai/gpt-4o-mini"
    ) -> None:
        self.timeout_s = timeout_s
        self.vision_model = vision_model
        self.model = model


class _FakeQdrantClient:
    def __init__(self, search_domain_fallback: bool) -> None:
        self.search_domain_fallback = search_domain_fallback


def _build_app(
    local_client: _FakeLocalClient,
    external_client: _FakeExternalClient,
    qdrant_client: _FakeQdrantClient,
    db_session,
    crawler_max_pages_default: int = 20,
    crawler_confidence_threshold: float = 0.7,
    image_internal_confidence: float = 0.30,
    image_external_confidence: float = 0.80,
    intent_router_provider: IntentRouterProvider = DEFAULT_INTENT_ROUTER_PROVIDER,
    tone_monitor_enabled: bool = True,
    tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER,
    rag_top_k: int = 3,
    rag_score_threshold: float = 0.35,
    local_llm_warmup_on_startup: bool = True,
    db_sessionmaker=None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(runtime_settings_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.state.local_client = local_client
    app.state.external_client = external_client
    app.state.qdrant_client = qdrant_client
    app.state.crawler_max_pages_default = crawler_max_pages_default
    app.state.crawler_confidence_threshold = crawler_confidence_threshold
    app.state.image_internal_confidence = image_internal_confidence
    app.state.image_external_confidence = image_external_confidence
    app.state.intent_router_provider = intent_router_provider
    app.state.tone_monitor_enabled = tone_monitor_enabled
    app.state.tone_monitor_provider = tone_monitor_provider
    app.state.rag_top_k = rag_top_k
    app.state.rag_score_threshold = rag_score_threshold
    app.state.local_llm_warmup_on_startup = local_llm_warmup_on_startup
    if db_sessionmaker is not None:
        app.state.db_sessionmaker = db_sessionmaker
    return app


def _build_default_app(
    db_session,
) -> tuple[FastAPI, _FakeLocalClient, _FakeExternalClient, _FakeQdrantClient]:
    local_client = _FakeLocalClient(temperature=None, timeout_s=30.0)
    external_client = _FakeExternalClient(timeout_s=30.0)
    qdrant_client = _FakeQdrantClient(search_domain_fallback=False)
    return (
        _build_app(local_client, external_client, qdrant_client, db_session),
        local_client,
        external_client,
        qdrant_client,
    )


async def test_get_sem_token_de_admin_e_403(db_session):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings")
    assert response.status_code == 403


async def test_get_devolve_valores_atuais_dos_clientes(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "local_llm_temperature": None,
        "local_llm_num_ctx": None,
        "local_llm_top_p": None,
        "local_llm_top_k": None,
        "local_llm_repeat_penalty": None,
        "local_llm_seed": None,
        "local_llm_timeout_s": 30.0,
        "external_llm_timeout_s": 30.0,
        "rag_top_k": 3,
        "rag_score_threshold": 0.35,
        "rag_search_domain_fallback": False,
        "crawler_max_pages_default": 20,
        "crawler_confidence_threshold": 0.7,
        "external_model_name": "openai/gpt-4o-mini",
        "external_vision_model_name": "",
        "image_internal_confidence": 0.30,
        "image_external_confidence": 0.80,
        "intent_router_provider": "heuristica_llm",
        "tone_monitor_enabled": True,
        "tone_monitor_provider": "heuristica_llm",
        "local_llm_keep_alive": "-1",
        "local_llm_warmup_on_startup": True,
        "local_model_loaded": False,
        "local_model_vram_bytes": None,
    }


async def test_put_atualiza_so_os_campos_enviados(db_session, admin_headers):
    app, local_client, external_client, qdrant_client = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_temperature": 0.2},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["local_llm_temperature"] == 0.2
    assert local_client.temperature == 0.2
    # Campos não enviados continuam com o valor original.
    assert local_client.timeout_s == 30.0
    assert external_client.timeout_s == 30.0
    assert qdrant_client.search_domain_fallback is False


async def test_put_com_temperatura_null_explicito_reseta_para_default_do_modelo(
    db_session, admin_headers
):
    app, local_client, *_ = _build_default_app(db_session)
    local_client.temperature = 0.5
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_temperature": None},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["local_llm_temperature"] is None
    assert local_client.temperature is None


async def test_put_atualiza_todos_os_campos_de_uma_vez(db_session, admin_headers):
    app, local_client, external_client, qdrant_client = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={
            "local_llm_temperature": 0.0,
            "local_llm_timeout_s": 60.0,
            "external_llm_timeout_s": 45.0,
            "rag_search_domain_fallback": True,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert local_client.temperature == 0.0
    assert local_client.timeout_s == 60.0
    assert external_client.timeout_s == 45.0
    assert qdrant_client.search_domain_fallback is True


async def test_put_temperatura_fora_do_intervalo_e_422(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_temperature": 5.0},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_put_timeout_zero_ou_negativo_e_422(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_timeout_s": 0.0},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_put_atualiza_crawler_max_pages_default(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"crawler_max_pages_default": 50},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["crawler_max_pages_default"] == 50
    assert app.state.crawler_max_pages_default == 50


async def test_put_atualiza_crawler_confidence_threshold(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"crawler_confidence_threshold": 0.5},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["crawler_confidence_threshold"] == 0.5
    assert app.state.crawler_confidence_threshold == 0.5


async def test_put_crawler_confidence_threshold_fora_do_intervalo_e_422(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"crawler_confidence_threshold": 1.5},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_put_crawler_max_pages_default_zero_ou_negativo_e_422(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"crawler_max_pages_default": 0},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_put_atualiza_external_vision_model_name(db_session, admin_headers):
    app, _, external_client, _ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"external_vision_model_name": "openai/gpt-4o-mini"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["external_vision_model_name"] == "openai/gpt-4o-mini"
    assert external_client.vision_model == "openai/gpt-4o-mini"


async def test_put_atualiza_limiares_de_identificacao_de_imagem(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"image_internal_confidence": 0.5, "image_external_confidence": 0.9},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["image_internal_confidence"] == 0.5
    assert response.json()["image_external_confidence"] == 0.9
    assert app.state.image_internal_confidence == 0.5
    assert app.state.image_external_confidence == 0.9


async def test_put_limiar_de_imagem_fora_do_intervalo_e_422(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"image_external_confidence": 1.5},
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_get_retorna_intent_router_provider_default(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["intent_router_provider"] == "heuristica_llm"


async def test_put_atualiza_intent_router_provider(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "jev_openrouter"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["intent_router_provider"] == "jev_openrouter"
    assert app.state.intent_router_provider == "jev_openrouter"

    # Confirma persistência em subsequente GET
    get_resp = client.get("/api/admin/runtime-settings", headers=admin_headers)
    assert get_resp.json()["intent_router_provider"] == "jev_openrouter"


async def test_put_atualiza_intent_router_provider_para_heuristica_llm(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "heuristica_llm"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["intent_router_provider"] == "heuristica_llm"
    assert app.state.intent_router_provider == "heuristica_llm"

    get_resp = client.get("/api/admin/runtime-settings", headers=admin_headers)
    assert get_resp.json()["intent_router_provider"] == "heuristica_llm"


async def test_put_atualiza_intent_router_provider_para_heuristica(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "heuristica"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["intent_router_provider"] == "heuristica"
    assert app.state.intent_router_provider == "heuristica"

    get_resp = client.get("/api/admin/runtime-settings", headers=admin_headers)
    assert get_resp.json()["intent_router_provider"] == "heuristica"


async def test_put_rejeita_intent_router_provider_invalido(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"intent_router_provider": "provedor_inexistente"},
        headers=admin_headers,
    )
    assert response.status_code == 422


async def test_get_runtime_settings_traz_defaults_do_monitor_de_tom(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["tone_monitor_enabled"] is True
    assert body["tone_monitor_provider"] == "heuristica_llm"


async def test_put_runtime_settings_atualiza_monitor_de_tom(db_session, admin_headers):
    app, *_ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"tone_monitor_enabled": False, "tone_monitor_provider": "jev_openrouter"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tone_monitor_enabled"] is False
    assert body["tone_monitor_provider"] == "jev_openrouter"


async def test_put_atualiza_external_model_name(db_session, admin_headers):
    app, _, ext_client, _ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"external_model_name": "anthropic/claude-3.5-sonnet"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["external_model_name"] == "anthropic/claude-3.5-sonnet"
    assert ext_client.model == "anthropic/claude-3.5-sonnet"


async def test_put_atualiza_keep_alive_e_sincroniza_ollama(db_session, admin_headers):
    app, local_client, _, _ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_keep_alive": "30m"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["local_llm_keep_alive"] == "30m"
    assert local_client.keep_alive == "30m"
    assert local_client.preloaded is True

    # Teste de descarregar com keep_alive == "0"
    response_unload = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_keep_alive": "0"},
        headers=admin_headers,
    )
    assert response_unload.status_code == 200
    assert response_unload.json()["local_llm_keep_alive"] == "0"
    assert local_client.keep_alive == "0"
    assert local_client.unloaded is True


async def test_put_atualiza_warmup_on_startup(db_session, admin_headers):
    app, _, _, _ = _build_default_app(db_session)
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"local_llm_warmup_on_startup": False},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["local_llm_warmup_on_startup"] is False
    assert app.state.local_llm_warmup_on_startup is False


async def test_post_preload_e_unload_endpoints(db_session, admin_headers):
    app, local_client, _, _ = _build_default_app(db_session)
    client = TestClient(app)

    # Preload
    resp_preload = client.post("/api/admin/runtime-settings/preload", headers=admin_headers)
    assert resp_preload.status_code == 200
    assert resp_preload.json()["local_model_loaded"] is True
    assert resp_preload.json()["local_model_vram_bytes"] == 8589934592
    assert local_client.preloaded is True

    # Unload
    resp_unload = client.post("/api/admin/runtime-settings/unload", headers=admin_headers)
    assert resp_unload.status_code == 200
    assert resp_unload.json()["local_model_loaded"] is False
    assert resp_unload.json()["local_model_vram_bytes"] is None
    assert local_client.unloaded is True


async def test_persistencia_de_runtime_settings_no_banco():
    from app.db.engine import create_db_engine, create_session_factory
    from app.db.models import Base
    from app.db.settings import get_all_app_settings

    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        admin = Cliente(nome="Admin Teste", email="admin@empresa.com")
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        admin_headers = {"Authorization": f"Bearer mock-token-{admin.id}"}

    async def _override_get_db_session():
        async with session_factory() as session:
            yield session

    local_client = _FakeLocalClient()
    ext_client = _FakeExternalClient(timeout_s=30.0)
    qdrant = _FakeQdrantClient(search_domain_fallback=False)
    app = FastAPI()
    app.include_router(runtime_settings_router)
    app.dependency_overrides[get_db_session] = _override_get_db_session
    app.state.local_client = local_client
    app.state.external_client = ext_client
    app.state.qdrant_client = qdrant
    app.state.crawler_max_pages_default = 20
    app.state.crawler_confidence_threshold = 0.7
    app.state.image_internal_confidence = 0.30
    app.state.image_external_confidence = 0.80
    app.state.intent_router_provider = DEFAULT_INTENT_ROUTER_PROVIDER
    app.state.tone_monitor_enabled = True
    app.state.tone_monitor_provider = DEFAULT_TONE_MONITOR_PROVIDER
    app.state.rag_top_k = 3
    app.state.rag_score_threshold = 0.35
    app.state.local_llm_warmup_on_startup = True
    app.state.db_sessionmaker = session_factory

    client = TestClient(app)
    response = client.put(
        "/api/admin/runtime-settings",
        json={
            "local_llm_keep_alive": "24h",
            "local_llm_warmup_on_startup": True,
            "local_llm_temperature": 0.35,
        },
        headers=admin_headers,
    )
    assert response.status_code == 200

    async with session_factory() as session:
        stored = await get_all_app_settings(session)
        assert stored["local_llm_keep_alive"] == "24h"
        assert stored["local_llm_warmup_on_startup"] is True
        assert stored["local_llm_temperature"] == 0.35

    await engine.dispose()
