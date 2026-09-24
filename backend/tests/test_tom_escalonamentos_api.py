from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag_dependencies import get_db_session
from app.api.tom_escalonamentos import router as tom_escalonamentos_router
from app.router.tone_monitor import criar_escalonamento


def _build_app(db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(tom_escalonamentos_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_get_escalonamentos_vazio_quando_nao_ha_casos(db_session):
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_escalonamentos_retorna_caso_persistido(db_session):
    await criar_escalonamento(
        db_session,
        conversation_id="conv-1",
        mensagem="preciso falar com um atendente AGORA",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["conversation_id"] == "conv-1"
    assert body[0]["motivo"] == "urgencia"
    assert body[0]["provider_efetivo"] == "heuristica_llm"


async def test_get_escalonamentos_ordena_mais_recente_primeiro(db_session):
    import asyncio

    await criar_escalonamento(
        db_session,
        conversation_id="conv-a",
        mensagem="primeira",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    await asyncio.sleep(1.1)
    await criar_escalonamento(
        db_session,
        conversation_id="conv-b",
        mensagem="segunda",
        motivo="insatisfacao",
        confianca=0.8,
        provider_efetivo="jev_openrouter",
    )
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    body = response.json()
    assert [r["conversation_id"] for r in body] == ["conv-b", "conv-a"]
