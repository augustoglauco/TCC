import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

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
def metrics_client(db_session):
    app = FastAPI()
    app.include_router(admin_metrics_router)
    app.state.db_sessionmaker = _SingleSessionMaker(db_session)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client



@pytest.mark.asyncio
async def test_metrics_api_requer_autenticacao_admin(metrics_client):
    response = metrics_client.get("/api/admin/metrics/tokens-and-costs?period=7d")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_metrics_api_empty_data(metrics_client, admin_headers):
    response = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=7d", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "7d"
    assert data["summary"]["total_closed_chats"] == 0
    assert data["summary"]["total_cost_usd"] == 0.0
    assert data["daily_breakdown"] == []


@pytest.mark.asyncio
async def test_metrics_api_aggregates_closed_chats_and_costs(
    metrics_client, db_session, admin_headers
):
    now = datetime.now(UTC)
    c1_encerrada_em = now - timedelta(hours=2)
    # O agrupamento diário bucketa no fuso local (America/Sao_Paulo, achado
    # da revisão de 2026-10-04), não em UTC — calcula a data esperada a partir
    # da data em que c1 foi efetivamente encerrada.
    date_str = c1_encerrada_em.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")

    # Conversa 1: Fechada hoje/recente, mensagens locais e externas
    c1 = Conversa(
        id="conv-metrics-1",
        status="encerrada",
        encerrada_em=c1_encerrada_em,
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
    res_7d = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=7d", headers=admin_headers
    )
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
    res_30d = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=30d", headers=admin_headers
    )
    assert res_30d.status_code == 200
    data_30d = res_30d.json()
    assert data_30d["summary"]["total_closed_chats"] == 2
    assert data_30d["summary"]["total_external_prompt_tokens"] == 700
    assert data_30d["summary"]["total_external_completion_tokens"] == 350
    assert pytest.approx(data_30d["summary"]["total_cost_usd"], 0.00001) == 0.0035
    assert len(data_30d["daily_breakdown"]) == 2


@pytest.mark.asyncio
async def test_metrics_api_start_date_invalida_e_400(metrics_client, admin_headers):
    # Achado da revisão de 2026-10-04: antes, uma data mal formada era
    # silenciosamente ignorada e a resposta caía no período default (7d)
    # sem avisar o administrador.
    response = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?start_date=not-a-date", headers=admin_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_metrics_api_end_date_invalida_e_400(metrics_client, admin_headers):
    response = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?end_date=31-12-2026", headers=admin_headers
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_metrics_api_agrupa_por_dia_no_fuso_local_nao_utc(
    metrics_client, db_session, admin_headers
):
    # Achado da revisão de 2026-10-04: bucketar em UTC cortava o dia às 21h
    # em horário de Brasília (America/Sao_Paulo, UTC-3) em vez da meia-noite
    # local. 01:30 UTC de um dia é 22:30 do dia ANTERIOR em São Paulo.
    encerrada_em_utc = datetime(2026, 10, 5, 1, 30, tzinfo=UTC)
    c1 = Conversa(
        id="conv-metrics-tz-1",
        status="encerrada",
        encerrada_em=encerrada_em_utc,
        motivo_encerramento="manual_usuario",
    )
    db_session.add(c1)
    await db_session.commit()

    response = metrics_client.get(
        "/api/admin/metrics/tokens-and-costs?period=all", headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()
    dias = [d["date"] for d in data["daily_breakdown"]]
    assert "2026-10-04" in dias
    assert "2026-10-05" not in dias
