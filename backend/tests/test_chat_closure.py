import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.chat import router as chat_router
from app.db.models import Conversa
from app.services.chat_closure_service import (
    fechar_conversa,
    fechar_conversas_inativas,
    inactivity_closure_worker,
)


class _SingleSessionMaker:
    def __init__(self, session) -> None:
        self._session = session
        self._lock = asyncio.Lock()

    def __call__(self):
        return self

    async def __aenter__(self):
        await self._lock.acquire()
        return self._session

    async def __aexit__(self, *exc_info) -> bool:
        self._lock.release()
        return False


@pytest.fixture
def chat_client(db_session):
    app = FastAPI()
    app.include_router(chat_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_inactivity_worker_closes_old_chats(db_session):
    old_chat = Conversa(
        id="old-chat-1",
        status="aberta",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=35),
    )
    recent_chat = Conversa(
        id="recent-chat-2",
        status="aberta",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=10),
    )
    already_closed = Conversa(
        id="closed-chat-3",
        status="encerrada",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=40),
        encerrada_em=datetime.now(UTC) - timedelta(minutes=40),
        motivo_encerramento="manual_usuario",
    )
    db_session.add_all([old_chat, recent_chat, already_closed])
    await db_session.commit()

    closed_count = await fechar_conversas_inativas(db_session, timeout_minutes=30)
    assert closed_count == 1

    await db_session.refresh(old_chat)
    await db_session.refresh(recent_chat)
    await db_session.refresh(already_closed)

    assert old_chat.status == "encerrada"
    assert old_chat.motivo_encerramento == "inatividade"
    assert old_chat.encerrada_em is not None

    assert recent_chat.status == "aberta"
    assert already_closed.status == "encerrada"
    assert already_closed.motivo_encerramento == "manual_usuario"


@pytest.mark.asyncio
async def test_inactivity_closure_worker_fecha_na_primeira_varredura_sem_esperar_o_intervalo(
    db_session,
):
    # Achado da revisão de 2026-10-04: a varredura só rodava DEPOIS do
    # primeiro `asyncio.sleep(interval_seconds)` — uma conversa já inativa
    # há mais de `timeout_minutes` no momento de um restart do backend
    # ficava aberta por até `interval_seconds` extras antes de ser
    # encerrada pela primeira vez.
    old_chat = Conversa(
        id="old-chat-worker-1",
        status="aberta",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=35),
    )
    db_session.add(old_chat)
    await db_session.commit()

    session_factory = _SingleSessionMaker(db_session)
    # Intervalo bem maior que o tempo de espera do teste: se a varredura só
    # rodasse depois do `sleep`, a conversa continuaria aberta.
    task = asyncio.create_task(
        inactivity_closure_worker(session_factory, interval_seconds=9999, timeout_minutes=30)
    )
    try:
        await asyncio.sleep(0.05)
    finally:
        task.cancel()
        # O worker captura `asyncio.CancelledError` internamente (loga e
        # retorna), então `await task` não a relança aqui.
        await task

    await db_session.refresh(old_chat)
    assert old_chat.status == "encerrada"
    assert old_chat.motivo_encerramento == "inatividade"


@pytest.mark.asyncio
async def test_fechar_conversa_manual_e_idempotente(db_session):
    chat = Conversa(
        id="chat-manual-1",
        status="aberta",
    )
    db_session.add(chat)
    await db_session.commit()

    # Fecha manualmente
    res = await fechar_conversa(db_session, "chat-manual-1", motivo="manual_usuario")
    assert res is not None
    assert res.status == "encerrada"
    assert res.motivo_encerramento == "manual_usuario"
    assert res.encerrada_em is not None

    # Chamada idempotente
    res2 = await fechar_conversa(db_session, "chat-manual-1", motivo="manual_usuario")
    assert res2 is not None
    assert res2.status == "encerrada"
    assert res2.motivo_encerramento == "manual_usuario"

    # Chat inexistente
    res_none = await fechar_conversa(db_session, "chat-inexistente")
    assert res_none is None


def test_api_close_conversation(chat_client, db_session):
    chat = Conversa(
        id="chat-api-123",
        status="aberta",
    )
    db_session.add(chat)
    # commit síncrono ou flush no session
    import asyncio
    asyncio.run(db_session.commit())

    response = chat_client.post(
        "/api/chat/conversations/chat-api-123/close", json={"motivo": "manual_usuario"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == "chat-api-123"
    assert data["status"] == "encerrada"
    assert data["motivo_encerramento"] == "manual_usuario"
    assert data["encerrada_em"] is not None

    # Idempotência via API
    response2 = chat_client.post("/api/chat/conversations/chat-api-123/close")
    assert response2.status_code == 200
    assert response2.json()["status"] == "encerrada"

    # 404 em conversa inexistente
    response_404 = chat_client.post("/api/chat/conversations/nao-existe/close")
    assert response_404.status_code == 404
