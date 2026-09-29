import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, Agendamento

@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()

async def test_criar_e_consultar_agendamento(factory):
    agora = datetime.now(timezone.utc)
    agendamento_id = uuid.uuid4()
    async with factory() as session:
        ag = Agendamento(
            id=agendamento_id,
            user_email="cliente@teste.com",
            nome_cliente="Carlos Teste",
            telefone="11999998888",
            data_hora_inicio=agora,
            data_hora_fim=agora,
            descricao="Visita técnica de gerador",
            status="confirmado",
            origem="chat",
            google_event_id="evt_123",
            google_event_link="https://calendar.google.com/event/123",
            conversation_id="conv_abc",
        )
        session.add(ag)
        await session.commit()

    async with factory() as session:
        resultado = await session.execute(
            select(Agendamento).where(Agendamento.id == agendamento_id)
        )
        recuperado = resultado.scalars().first()
        assert recuperado is not None
        assert recuperado.user_email == "cliente@teste.com"
        assert recuperado.status == "confirmado"
        assert recuperado.origem == "chat"
        assert recuperado.google_event_id == "evt_123"
