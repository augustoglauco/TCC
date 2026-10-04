import asyncio
from datetime import UTC, datetime, timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.admin_metrics import router as admin_metrics_router
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
def metrics_client(db_session):
    app = FastAPI()
    app.include_router(admin_metrics_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_metrics_api_empty_data(metrics_client):
    response = metrics_client.get("/api/admin/metrics/tokens-and-costs?period=7d")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "7d"
    assert data["summary"]["total_closed_chats"] == 0
    assert data["summary"]["total_cost_usd"] == 0.0
    assert data["daily_breakdown"] == []


@pytest.mark.asyncio
async def test_metrics_api_aggregates_closed_chats_and_costs(metrics_client, db_session):
    now = datetime.now(UTC)
    date_str = now.strftime("%Y-%m-%d")

    # Conversa 1: Fechada hoje, mensagens locais e externas
    c1 = Conversa(
        id="conv-metrics-1",
        status="encerrada",
        encerrada_em=now - timedelta(hours=2),
        motivo_encerramento="manual_usuario",
    )
    # Conversa 2: Aberta (NÃO deve entrar nas métricas de chats encerrados)
    c2 = Conversa(
        id="conv-metrics-2",
        status="aberta",
    )
    # Conversa 3: Fechada há 15 dias (fora de 7d, mas dentro de 30d)
    c3 = Conversa(
        id="conv-metrics-3",
        status="encerrada",
        encerrada_em=now - timedelta(days=15),
        motivo_encerramento="inatividade",
    )

    db_session.add_all([c1, c2, c3])
    await db_session.flush()

    m1_user = ConversaMensagem(
        conversa_id="conv-metrics-1",
        papel="cliente",
        texto="ola",
    )
    # Mensagem local
    m1_assist_local = ConversaMensagem(
        conversa_id="conv-metrics-1",
        papel="assistente",
        texto="resposta local",
        metricas={
            "backend_used": "local",
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cost_prompt_usd": 0.0,
            "cost_completion_usd": 0.0,
            "estimated_cost_usd": 0.0,
        },
    )
    # Mensagem externa
    m1_assist_ext = ConversaMensagem(
        conversa_id="conv-metrics-1",
        papel="assistente",
        texto="resposta externa",
        metricas={
            "backend_used": "externo",
            "prompt_tokens": 200,
            "completion_tokens": 100,
            "cost_prompt_usd": 0.0004,
            "cost_completion_usd": 0.0006,
            "estimated_cost_usd": 0.0010,
        },
    )

    # Mensagem para conversa c3 (fora de 7d)
    m3_assist_ext = ConversaMensagem(
        conversa_id="conv-metrics-3",
        papel="assistente",
        texto="resposta c3",
        metricas={
            "backend_used": "externo",
            "prompt_tokens": 500,
            "completion_tokens": 250,
            "cost_prompt_usd": 0.0010,
            "cost_completion_usd": 0.0015,
            "estimated_cost_usd": 0.0025,
        },
    )

    db_session.add_all([m1_user, m1_assist_local, m1_assist_ext, m3_assist_ext])
    await db_session.commit()

    # Consulta período 7d
    res_7d = metrics_client.get("/api/admin/metrics/tokens-and-costs?period=7d")
    assert res_7d.status_code == 200
    data_7d = res_7d.json()
    assert data_7d["summary"]["total_closed_chats"] == 1
    assert data_7d["summary"]["total_internal_prompt_tokens"] == 100
    assert data_7d["summary"]["total_internal_completion_tokens"] == 50
    assert data_7d["summary"]["total_external_prompt_tokens"] == 200
    assert data_7d["summary"]["total_external_completion_tokens"] == 100
    assert pytest.approx(data_7d["summary"]["total_cost_prompt_usd"], 0.00001) == 0.0004
    assert pytest.approx(data_7d["summary"]["total_cost_completion_usd"], 0.00001) == 0.0006
    assert pytest.approx(data_7d["summary"]["total_cost_usd"], 0.00001) == 0.0010

    assert len(data_7d["daily_breakdown"]) == 1
    day = data_7d["daily_breakdown"][0]
    assert day["date"] == date_str
    assert day["closed_chats_count"] == 1
    assert day["internal_prompt_tokens"] == 100
    assert day["external_prompt_tokens"] == 200

    # Consulta período 30d (deve incluir c1 e c3)
    res_30d = metrics_client.get("/api/admin/metrics/tokens-and-costs?period=30d")
    assert res_30d.status_code == 200
    data_30d = res_30d.json()
    assert data_30d["summary"]["total_closed_chats"] == 2
    assert data_30d["summary"]["total_external_prompt_tokens"] == 700
    assert data_30d["summary"]["total_external_completion_tokens"] == 350
    assert pytest.approx(data_30d["summary"]["total_cost_usd"], 0.00001) == 0.0035
    assert len(data_30d["daily_breakdown"]) == 2
