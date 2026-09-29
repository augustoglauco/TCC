import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Agendamento
from app.mcp_client.google_calendar import GoogleCalendarMCPClient


class _FakeCalendarClient:
    def __init__(self, available: bool = True):
        self.available = available
        self.deleted_events: list[str] = []
        self.created_events: list[dict] = []
        self.mock_events = [
            {"id": "evt_google_1", "summary": "Visita Técnica", "start": "2026-10-10T10:00:00Z"}
        ]

    async def is_time_available(self, start: datetime, end: datetime) -> bool:
        return self.available

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> tuple[str, str]:
        self.created_events.append({
            "summary": summary,
            "start": start,
            "end": end,
            "attendee_email": attendee_email,
            "attendee_name": attendee_name,
            "description": description,
        })
        return "evt_fake_mcp", "https://calendar.google.com/evt_fake_mcp"

    async def delete_event(self, event_id: str) -> bool:
        self.deleted_events.append(event_id)
        return True

    async def list_events(self, time_min: datetime, time_max: datetime) -> list[dict]:
        return self.mock_events


@pytest.fixture
def fake_calendar(app_sqlite):
    fake = _FakeCalendarClient(available=True)
    app_sqlite.state.calendar_client = fake
    return fake


@pytest.mark.asyncio
async def test_listar_meus_agendamentos_filtra_por_usuario(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    ag1 = Agendamento(
        id=uuid.uuid4(),
        user_email="user1@example.com",
        nome_cliente="User 1",
        data_hora_inicio=agora + timedelta(days=1),
        data_hora_fim=agora + timedelta(days=1, hours=1),
        status="confirmado",
        origem="chat",
    )
    ag2 = Agendamento(
        id=uuid.uuid4(),
        user_email="user1@example.com",
        nome_cliente="User 1",
        data_hora_inicio=agora + timedelta(days=2),
        data_hora_fim=agora + timedelta(days=2, hours=1),
        status="cancelado",
        origem="chat",
    )
    ag3 = Agendamento(
        id=uuid.uuid4(),
        user_email="outro@example.com",
        nome_cliente="Outro",
        data_hora_inicio=agora + timedelta(days=3),
        data_hora_fim=agora + timedelta(days=3, hours=1),
        status="confirmado",
        origem="chat",
    )
    db_session.add_all([ag1, ag2, ag3])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.get("/api/agendamentos/meus?user_email=user1@example.com")
        assert resp.status_code == 200
        dados = resp.json()
        assert len(dados) == 2
        # Ordenado por data_hora_inicio DESC -> ag2 antes de ag1
        assert dados[0]["id"] == str(ag2.id)
        assert dados[1]["id"] == str(ag1.id)
        assert all(item["user_email"] == "user1@example.com" for item in dados)


@pytest.mark.asyncio
async def test_cancelar_agendamento_proprio_com_sucesso(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    ag = Agendamento(
        id=uuid.uuid4(),
        user_email="user1@example.com",
        nome_cliente="User 1",
        data_hora_inicio=agora + timedelta(days=1),
        data_hora_fim=agora + timedelta(days=1, hours=1),
        status="confirmado",
        origem="chat",
        google_event_id="evt_canc_1",
    )
    db_session.add(ag)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post(f"/api/agendamentos/{ag.id}/cancelar?user_email=user1@example.com")
        assert resp.status_code == 200
        dados = resp.json()
        assert dados["status"] == "cancelado"
        assert "evt_canc_1" in fake_calendar.deleted_events


@pytest.mark.asyncio
async def test_cancelar_agendamento_de_outro_usuario_retorna_403(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    ag = Agendamento(
        id=uuid.uuid4(),
        user_email="dono@example.com",
        nome_cliente="Dono",
        data_hora_inicio=agora + timedelta(days=1),
        data_hora_fim=agora + timedelta(days=1, hours=1),
        status="confirmado",
    )
    db_session.add(ag)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post(f"/api/agendamentos/{ag.id}/cancelar?user_email=invasor@example.com")
        assert resp.status_code == 403
        assert "permissão" in resp.json()["detail"].lower() or "forbidden" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cancelar_agendamento_ja_cancelado_retorna_400(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    ag = Agendamento(
        id=uuid.uuid4(),
        user_email="user1@example.com",
        nome_cliente="User 1",
        data_hora_inicio=agora + timedelta(days=1),
        data_hora_fim=agora + timedelta(days=1, hours=1),
        status="cancelado",
    )
    db_session.add(ag)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post(f"/api/agendamentos/{ag.id}/cancelar?user_email=user1@example.com")
        assert resp.status_code == 400
        assert "cancelado" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_listar_todos_agendamentos(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    ag1 = Agendamento(
        id=uuid.uuid4(),
        user_email="clienteA@teste.com",
        nome_cliente="Cliente A",
        data_hora_inicio=agora + timedelta(days=1),
        data_hora_fim=agora + timedelta(days=1, hours=1),
        status="confirmado",
        origem="chat",
    )
    ag2 = Agendamento(
        id=uuid.uuid4(),
        user_email="clienteB@teste.com",
        nome_cliente="Cliente B",
        data_hora_inicio=agora + timedelta(days=2),
        data_hora_fim=agora + timedelta(days=2, hours=1),
        status="cancelado",
        origem="manual_admin",
    )
    db_session.add_all([ag1, ag2])
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.get("/api/agendamentos/admin")
        assert resp.status_code == 200
        dados = resp.json()
        assert len(dados) == 2

        # Teste com filtro por status
        resp_conf = await client.get("/api/agendamentos/admin?status=confirmado")
        assert resp_conf.status_code == 200
        dados_conf = resp_conf.json()
        assert len(dados_conf) == 1
        assert dados_conf[0]["id"] == str(ag1.id)

        # Teste com filtro por email
        resp_email = await client.get("/api/agendamentos/admin?filtro_email=clienteB")
        assert resp_email.status_code == 200
        dados_email = resp_email.json()
        assert len(dados_email) == 1
        assert dados_email[0]["id"] == str(ag2.id)


@pytest.mark.asyncio
async def test_admin_criar_agendamento_manual(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    data_inicio = agora + timedelta(days=5)

    payload = {
        "user_email": "manual@cliente.com",
        "nome_cliente": "Carlos Manual",
        "telefone": "11988887777",
        "data_hora_inicio": data_inicio.isoformat(),
        "descricao": "Visita comercial técnica",
    }

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post("/api/agendamentos/admin/manual", json=payload)
        assert resp.status_code == 201
        dados = resp.json()
        assert dados["user_email"] == "manual@cliente.com"
        assert dados["nome_cliente"] == "Carlos Manual"
        assert dados["origem"] == "manual_admin"
        assert dados["status"] == "confirmado"
        assert dados["google_event_id"] == "evt_fake_mcp"
        assert len(fake_calendar.created_events) == 1
        # Valida que o padrão agora é 60 minutos (1 hora)
        inicio = datetime.fromisoformat(dados["data_hora_inicio"])
        fim = datetime.fromisoformat(dados["data_hora_fim"])
        assert fim - inicio == timedelta(minutes=60)
        assert fake_calendar.created_events[0]["end"] - fake_calendar.created_events[0]["start"] == timedelta(minutes=60)


@pytest.mark.asyncio
async def test_admin_criar_agendamento_manual_com_duracao_customizada(app_sqlite, db_session, fake_calendar):
    agora = datetime.now(timezone.utc)
    data_inicio = agora + timedelta(days=6)

    payload = {
        "user_email": "custom@cliente.com",
        "nome_cliente": "Ana Custom",
        "data_hora_inicio": data_inicio.isoformat(),
        "duracao_minutos": 45,
    }

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post("/api/agendamentos/admin/manual", json=payload)
        assert resp.status_code == 201
        dados = resp.json()
        inicio = datetime.fromisoformat(dados["data_hora_inicio"])
        fim = datetime.fromisoformat(dados["data_hora_fim"])
        assert fim - inicio == timedelta(minutes=45)



@pytest.mark.asyncio
async def test_admin_criar_agendamento_manual_conflito_retorna_409(app_sqlite, db_session, fake_calendar):
    fake_calendar.available = False
    agora = datetime.now(timezone.utc)

    payload = {
        "user_email": "conflito@cliente.com",
        "nome_cliente": "Cliente Conflito",
        "data_hora_inicio": (agora + timedelta(days=2)).isoformat(),
    }

    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.post("/api/agendamentos/admin/manual", json=payload)
        assert resp.status_code == 409
        assert "indisponível" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_admin_consultar_eventos_google(app_sqlite, fake_calendar):
    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as client:
        resp = await client.get("/api/agendamentos/admin/google-events")
        assert resp.status_code == 200
        dados = resp.json()
        assert len(dados) == 1
        assert dados[0]["id"] == "evt_google_1"
