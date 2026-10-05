import pytest
from datetime import datetime, UTC
from sqlalchemy import select
from app.db.models import Conversa, ConversaMensagem

@pytest.mark.asyncio
async def test_conversa_atendimento_humano_fields(db_session):
    now = datetime.now(UTC)
    conversa = Conversa(
        id="conv-transbordo-test-1",
        status="aguardando_humano",
        atendente_id="op_123",
        atendente_nome="Carlos Suporte",
        motivo_escalonamento="tom_frustrado",
        prioridade=5,
        escalado_em=now,
    )
    db_session.add(conversa)
    await db_session.flush()

    msg = ConversaMensagem(
        conversa_id="conv-transbordo-test-1",
        papel="atendente",
        atendente_nome="Carlos Suporte",
        texto="Olá! Sou o Carlos e assumi seu atendimento. Como posso ajudar?",
    )
    db_session.add(msg)
    await db_session.commit()

    saved_conv = await db_session.get(Conversa, "conv-transbordo-test-1")
    assert saved_conv is not None
    assert saved_conv.status == "aguardando_humano"
    assert saved_conv.atendente_id == "op_123"
    assert saved_conv.atendente_nome == "Carlos Suporte"
    assert saved_conv.motivo_escalonamento == "tom_frustrado"
    assert saved_conv.prioridade == 5
    assert saved_conv.escalado_em is not None

    stmt = select(ConversaMensagem).where(ConversaMensagem.conversa_id == "conv-transbordo-test-1")
    res = await db_session.execute(stmt)
    saved_msg = res.scalar_one()
    assert saved_msg.papel == "atendente"
    assert saved_msg.atendente_nome == "Carlos Suporte"
