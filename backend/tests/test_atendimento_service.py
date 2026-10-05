import pytest
from datetime import datetime, UTC
from sqlalchemy import select
from app.db.models import Conversa, ConversaMensagem
from app.services import atendimento_service

@pytest.mark.asyncio
async def test_escalar_para_humano_atualiza_status(db_session):
    c = Conversa(id="conv-serv-1", status="aberta")
    db_session.add(c)
    await db_session.commit()

    conv = await atendimento_service.escalar_para_humano(
        db_session,
        conversation_id="conv-serv-1",
        motivo="tom_frustrado",
        prioridade=5,
    )
    assert conv.status == "aguardando_humano"
    assert conv.motivo_escalonamento == "tom_frustrado"
    assert conv.prioridade == 5
    assert conv.escalado_em is not None


@pytest.mark.asyncio
async def test_escalar_para_humano_cria_conversa_se_nao_existir(db_session):
    conv = await atendimento_service.escalar_para_humano(
        db_session,
        conversation_id="conv-serv-nova-1",
        motivo="solicitacao_direta",
        prioridade=3,
    )
    assert conv.id == "conv-serv-nova-1"
    assert conv.status == "aguardando_humano"
    assert conv.motivo_escalonamento == "solicitacao_direta"
    assert conv.prioridade == 3


@pytest.mark.asyncio
async def test_claim_conversa_atomico_e_prevencao_concorrencia(db_session):
    c = Conversa(
        id="conv-claim-1",
        status="aguardando_humano",
        prioridade=5,
        escalado_em=datetime.now(UTC),
    )
    db_session.add(c)
    await db_session.commit()

    # Primeiro claim por Atendente 1: deve suceder
    sucesso1 = await atendimento_service.claim_conversa(
        db_session,
        conversation_id="conv-claim-1",
        atendente_id="atendente_1",
        atendente_nome="Mariana Atendente",
    )
    assert sucesso1 is True

    # Segundo claim por Atendente 2: deve falhar (retornar False)
    sucesso2 = await atendimento_service.claim_conversa(
        db_session,
        conversation_id="conv-claim-1",
        atendente_id="atendente_2",
        atendente_nome="Roberto Atendente",
    )
    assert sucesso2 is False

    # Verificar no banco que quem está associado é o Atendente 1
    reloaded = await db_session.get(Conversa, "conv-claim-1")
    assert reloaded.status == "em_atendimento_humano"
    assert reloaded.atendente_id == "atendente_1"
    assert reloaded.atendente_nome == "Mariana Atendente"


@pytest.mark.asyncio
async def test_listar_fila_espera_ordena_por_prioridade_e_tempo(db_session):
    now = datetime.now(UTC)
    c_baixa = Conversa(
        id="conv-baixa",
        status="aguardando_humano",
        prioridade=1,
        escalado_em=now,
    )
    c_critica = Conversa(
        id="conv-critica",
        status="aguardando_humano",
        prioridade=5,
        escalado_em=now,
    )
    db_session.add_all([c_baixa, c_critica])
    await db_session.commit()

    fila = await atendimento_service.listar_fila_espera(db_session)
    assert len(fila) >= 2
    # A conversa crítica (prioridade 5) deve vir antes da baixa (prioridade 1)
    ids = [item["id"] for item in fila]
    assert ids.index("conv-critica") < ids.index("conv-baixa")


@pytest.mark.asyncio
async def test_enviar_mensagem_atendente(db_session):
    c = Conversa(id="conv-msg-1", status="em_atendimento_humano", atendente_id="op_1")
    db_session.add(c)
    await db_session.commit()

    msg = await atendimento_service.enviar_mensagem_atendente(
        db_session,
        conversation_id="conv-msg-1",
        atendente_nome="Operador Teste",
        texto="Boa tarde! Em que posso ajudar?",
    )
    assert msg.id is not None
    assert msg.papel == "atendente"
    assert msg.atendente_nome == "Operador Teste"
    assert msg.texto == "Boa tarde! Em que posso ajudar?"


@pytest.mark.asyncio
async def test_finalizar_atendimento_encerra_conversa(db_session):
    c = Conversa(id="conv-fim-1", status="em_atendimento_humano", atendente_id="op_1")
    db_session.add(c)
    await db_session.commit()

    conv = await atendimento_service.finalizar_atendimento(
        db_session,
        conversation_id="conv-fim-1",
        motivo="resolvido_humano",
    )
    assert conv.status == "encerrada"
    assert conv.motivo_encerramento == "resolvido_humano"
    assert conv.encerrada_em is not None


@pytest.mark.asyncio
async def test_devolver_para_ia_reseta_status(db_session):
    c = Conversa(
        id="conv-devolver-1",
        status="em_atendimento_humano",
        atendente_id="op_1",
        atendente_nome="Operador",
        motivo_escalonamento="tom_frustrado",
    )
    db_session.add(c)
    await db_session.commit()

    conv = await atendimento_service.devolver_para_ia(
        db_session,
        conversation_id="conv-devolver-1",
    )
    assert conv.status == "aberta"
    assert conv.atendente_id is None
    assert conv.atendente_nome is None
    assert conv.motivo_escalonamento is None
