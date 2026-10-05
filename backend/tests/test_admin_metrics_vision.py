import asyncio
from datetime import UTC, datetime
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_metrics import router as admin_metrics_router
from app.api.rag_dependencies import get_db_session
from app.db.models import Conversa, ConversaMensagem


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
def vision_metrics_client(db_session):
    app = FastAPI()
    app.include_router(admin_metrics_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_metrics_api_segregates_vision_and_text(
    vision_metrics_client, db_session, admin_headers
):
    agora = datetime.now(UTC)

    # 1 conversa encerrada com 1 mensagem de visão e 1 mensagem de texto puro
    conversa = Conversa(
        id="conv-vision-test-1",
        status="encerrada",
        encerrada_em=agora,
        motivo_encerramento="manual_usuario",
    )
    db_session.add(conversa)

    # Mensagem 1: Visão Computacional (identificação de imagem)
    msg_vision = ConversaMensagem(
        conversa_id=conversa.id,
        papel="assistente",
        texto="Identifiquei o produto com sucesso!",
        criada_em=agora,
        metricas={
            "backend_used": "identificacao_imagem",
            "vision_used": True,
            "prompt_tokens": 1200,
            "completion_tokens": 150,
            "cost_prompt_usd": 0.0012,
            "cost_completion_usd": 0.0003,
            "estimated_cost_usd": 0.0015,
        },
    )

    # Mensagem 2: Resposta de texto padrão externa
    msg_text = ConversaMensagem(
        conversa_id=conversa.id,
        papel="assistente",
        texto="Posso te ajudar com mais alguma coisa?",
        criada_em=agora,
        metricas={
            "backend_used": "externo",
            "prompt_tokens": 400,
            "completion_tokens": 50,
            "cost_prompt_usd": 0.0004,
            "cost_completion_usd": 0.0001,
            "estimated_cost_usd": 0.0005,
        },
    )

    db_session.add_all([msg_vision, msg_text])
    await db_session.commit()

    response = vision_metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=today", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()

    summary = data["summary"]
    # Total de chats encerrados
    assert summary["total_closed_chats"] == 1

    # Totais globais
    assert summary["total_external_prompt_tokens"] == 1600  # 1200 + 400
    assert summary["total_external_completion_tokens"] == 200  # 150 + 50
    assert summary["total_cost_usd"] == 0.0020  # 0.0015 + 0.0005

    # Segregação específica de Visão Computacional
    assert summary["total_vision_calls"] == 1
    assert summary["total_vision_tokens"] == 1350  # 1200 prompt + 150 comp
    assert summary["total_vision_cost_usd"] == 0.0015

    # Detalhamento diário
    assert len(data["daily_breakdown"]) == 1
    daily = data["daily_breakdown"][0]
    assert daily["closed_chats_count"] == 1
    assert daily["vision_calls_count"] == 1
    assert daily["vision_cost_usd"] == 0.0015
    assert daily["total_cost_usd"] == 0.0020
