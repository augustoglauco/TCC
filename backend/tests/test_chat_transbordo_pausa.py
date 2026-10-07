import asyncio
import json
import pytest
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.chat import (
    router as chat_router,
    get_local_client,
    get_external_client,
    get_rag_client,
    get_rag_client_admin,
    get_stt_client,
    get_clip_store,
    get_clip_embedder,
    get_calendar_client,
    get_scheduling_config,
    get_sales_catalog_client,
    get_intent_router_provider,
    get_tone_monitor_enabled,
    get_tone_monitor_provider,
)
from app.db.models import Conversa, ConversaMensagem
from app.router.orchestrator import TokenEvent, RouterDecision, EscalonamentoEvent


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


def _parse_sse(texto: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in texto.strip().split("\n\n"):
        tipo = dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                try:
                    dados = json.loads(linha[len("data:") :].strip())
                except Exception:
                    dados = linha[len("data:") :].strip()
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos


@pytest.fixture
def chat_client(db_session):
    app = FastAPI()
    app.include_router(chat_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.state.complexity_strategy = "regras"
    app.state.image_internal_confidence = 0.8
    app.state.image_external_confidence = 0.6

    # Dummies para dependencies
    mock_local = MagicMock()
    mock_ext = MagicMock()
    mock_rag = MagicMock()
    mock_rag_admin = MagicMock()
    mock_stt = MagicMock()
    mock_stt.transcribe = AsyncMock(return_value="")
    mock_clip_store = MagicMock()
    mock_clip_embedder = MagicMock()
    mock_calendar = MagicMock()
    mock_sched = MagicMock()
    mock_catalog = MagicMock()

    app.dependency_overrides[get_local_client] = lambda: mock_local
    app.dependency_overrides[get_external_client] = lambda: mock_ext
    app.dependency_overrides[get_rag_client] = lambda: mock_rag
    app.dependency_overrides[get_rag_client_admin] = lambda: mock_rag_admin
    app.dependency_overrides[get_stt_client] = lambda: mock_stt
    app.dependency_overrides[get_clip_store] = lambda: mock_clip_store
    app.dependency_overrides[get_clip_embedder] = lambda: mock_clip_embedder
    app.dependency_overrides[get_calendar_client] = lambda: mock_calendar
    app.dependency_overrides[get_scheduling_config] = lambda: mock_sched
    app.dependency_overrides[get_sales_catalog_client] = lambda: mock_catalog
    app.dependency_overrides[get_intent_router_provider] = lambda: "heuristica_llm"
    app.dependency_overrides[get_tone_monitor_enabled] = lambda: True
    app.dependency_overrides[get_tone_monitor_provider] = lambda: "heuristica_llm"

    with TestClient(app) as client:
        yield client


@pytest.mark.asyncio
async def test_chat_pausado_quando_aguardando_humano(chat_client, db_session):
    c = Conversa(
        id="conv-pausa-1",
        status="aguardando_humano",
        prioridade=5,
        motivo_escalonamento="tom_frustrado",
        escalado_em=datetime.now(UTC),
    )
    db_session.add(c)
    await db_session.commit()

    # Envia mensagem para conversa pausada
    res = chat_client.post(
        "/api/chat/messages",
        json={"conversation_id": "conv-pausa-1", "message": "Ainda estou aguardando!"},
    )
    assert res.status_code == 200
    eventos = _parse_sse(res.text)
    tipos = [t for t, _ in eventos]

    # Deve emitir status com aguardando_humano e done, sem chamar LLM
    assert "status" in tipos
    status_data = next(d for t, d in eventos if t == "status")
    assert status_data["status"] == "aguardando_humano"
    assert "done" in tipos

    # Deve ter gravado a mensagem do cliente no banco
    stmt = (
        select(ConversaMensagem)
        .where(ConversaMensagem.conversa_id == "conv-pausa-1")
        .order_by(ConversaMensagem.id.desc())
    )
    res_db = await db_session.execute(stmt)
    msg = res_db.scalars().first()
    assert msg is not None
    assert msg.papel == "cliente"
    assert msg.texto == "Ainda estou aguardando!"


@pytest.mark.asyncio
async def test_chat_pausado_quando_em_atendimento_humano(chat_client, db_session):
    c = Conversa(
        id="conv-pausa-2",
        status="em_atendimento_humano",
        atendente_id="op_99",
        atendente_nome="Fernanda Suporte",
    )
    db_session.add(c)
    await db_session.commit()

    res = chat_client.post(
        "/api/chat/messages",
        json={"conversation_id": "conv-pausa-2", "message": "Oi Fernanda, deu certo?"},
    )
    assert res.status_code == 200
    eventos = _parse_sse(res.text)
    tipos = [t for t, _ in eventos]

    assert "status" in tipos
    status_data = next(d for t, d in eventos if t == "status")
    assert status_data["status"] == "em_atendimento_humano"
    assert status_data["atendente_nome"] == "Fernanda Suporte"

    stmt = (
        select(ConversaMensagem)
        .where(ConversaMensagem.conversa_id == "conv-pausa-2")
        .order_by(ConversaMensagem.id.desc())
    )
    res_db = await db_session.execute(stmt)
    msg = res_db.scalars().first()
    assert msg is not None
    assert msg.texto == "Oi Fernanda, deu certo?"


@pytest.mark.asyncio
async def test_solicitar_transbordo_endpoint(chat_client, db_session):
    c = Conversa(id="conv-solicitar-1", status="aberta")
    db_session.add(c)
    await db_session.commit()

    res = chat_client.post("/api/chat/conversations/conv-solicitar-1/transbordo")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "aguardando_humano"
    assert data["motivo_escalonamento"] == "solicitacao_direta"

    reloaded = await db_session.get(Conversa, "conv-solicitar-1")
    assert reloaded.status == "aguardando_humano"
    assert reloaded.motivo_escalonamento == "solicitacao_direta"


@pytest.mark.asyncio
async def test_conversation_history_endpoint_inclui_mensagem_do_atendente(chat_client, db_session):
    """Regressão de 2026-10-06: `ConversaMensagemOut.papel` não incluía
    `"atendente"` — `GET /api/chat/conversations/{id}` quebrava com 500
    (ValidationError) assim que havia uma mensagem do atendente na conversa,
    derrubando o histórico inteiro para o cliente que reabria/recarregava o
    chat (ele nunca via a resposta do atendente nem o restante da conversa)."""
    c = Conversa(id="conv-historico-atendente", status="em_atendimento_humano", atendente_id="op_1")
    db_session.add(c)
    await db_session.commit()

    db_session.add(
        ConversaMensagem(
            conversa_id="conv-historico-atendente", papel="cliente", texto="Preciso de ajuda"
        )
    )
    db_session.add(
        ConversaMensagem(
            conversa_id="conv-historico-atendente",
            papel="atendente",
            atendente_nome="Fernanda Suporte",
            texto="Olá! Em que posso ajudar?",
        )
    )
    await db_session.commit()

    res = chat_client.get("/api/chat/conversations/conv-historico-atendente")
    assert res.status_code == 200
    mensagens = res.json()["mensagens"]
    assert [m["papel"] for m in mensagens] == ["cliente", "atendente"]
    atendente_msg = mensagens[1]
    assert atendente_msg["texto"] == "Olá! Em que posso ajudar?"
    assert atendente_msg["atendente_nome"] == "Fernanda Suporte"
