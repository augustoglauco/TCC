"""Memória da conversa no Postgres (R9, Fase 6) — `app.memory.store`."""

import pytest

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.memory.store import (
    carregar_contexto,
    contar_mensagens,
    limpar_conversa,
    listar_mensagens,
    obter_contexto_conversa_anterior,
    registrar_email,
    registrar_troca,
)


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


async def test_conversa_nova_tem_contexto_vazio(factory):
    async with factory() as session:
        contexto = await carregar_contexto(session, "conv-inexistente")

    assert contexto.mensagens_recentes == []
    assert contexto.resumo is None
    assert contexto.email is None


async def test_registrar_troca_grava_cliente_e_assistente_em_ordem(factory):
    async with factory() as session:
        await registrar_troca(session, "conv-1", "Quanto custa o GD-15?", "R$ 24.900,00", "vendas")
        await registrar_troca(session, "conv-1", "E o GD-30?", "R$ 42.500,00", "vendas")

    async with factory() as session:
        mensagens = await listar_mensagens(session, "conv-1")
        total = await contar_mensagens(session, "conv-1")

    assert [(m.papel, m.texto, m.dominio) for m in mensagens] == [
        ("cliente", "Quanto custa o GD-15?", None),
        ("assistente", "R$ 24.900,00", "vendas"),
        ("cliente", "E o GD-30?", None),
        ("assistente", "R$ 42.500,00", "vendas"),
    ]
    assert total == 4


async def test_contexto_traz_as_ultimas_tres_mensagens_do_cliente_mais_antiga_primeiro(factory):
    async with factory() as session:
        for i in range(1, 6):
            await registrar_troca(session, "conv-2", f"pergunta {i}", f"resposta {i}", "suporte")

    async with factory() as session:
        contexto = await carregar_contexto(session, "conv-2")

    # Mesmo conteúdo do histórico em memória que isto substitui: só as
    # mensagens do cliente, as 3 mais recentes.
    assert contexto.mensagens_recentes == ["pergunta 3", "pergunta 4", "pergunta 5"]


async def test_conversas_nao_se_misturam(factory):
    async with factory() as session:
        await registrar_troca(session, "conv-a", "mensagem de A", "resposta A", "vendas")
        await registrar_troca(session, "conv-b", "mensagem de B", "resposta B", "suporte")

    async with factory() as session:
        contexto_a = await carregar_contexto(session, "conv-a")
        mensagens_b = await listar_mensagens(session, "conv-b")

    assert contexto_a.mensagens_recentes == ["mensagem de A"]
    assert [m.texto for m in mensagens_b] == ["mensagem de B", "resposta B"]


async def test_listar_mensagens_respeita_o_limite_e_devolve_as_mais_recentes(factory):
    async with factory() as session:
        for i in range(1, 4):
            await registrar_troca(session, "conv-3", f"p{i}", f"r{i}", "vendas")

    async with factory() as session:
        mensagens = await listar_mensagens(session, "conv-3", limite=3)

    assert [m.texto for m in mensagens] == ["r2", "p3", "r3"]


async def test_limpar_conversa_deleta_mensagens_e_reseta_resumo(factory):
    async with factory() as session:
        await registrar_troca(session, "conv-del", "olá", "oi", "vendas")

    async with factory() as session:
        ok = await limpar_conversa(session, "conv-del")
        assert ok is True

    async with factory() as session:
        total = await contar_mensagens(session, "conv-del")
        contexto = await carregar_contexto(session, "conv-del")
        assert total == 0
        assert contexto.resumo is None
        assert contexto.mensagens_recentes == []


async def test_contexto_traz_a_ultima_troca_cliente_e_assistente(factory):
    async with factory() as session:
        await registrar_troca(session, "conv-t", "p1", "r1", "vendas")
        await registrar_troca(
            session, "conv-t", "[imagem enviada]", "Identifiquei: RC 4102g2.", "vendas"
        )

    async with factory() as session:
        contexto = await carregar_contexto(session, "conv-t")

    assert contexto.ultima_troca == ("[imagem enviada]", "Identifiquei: RC 4102g2.")


async def test_conversa_nova_nao_tem_ultima_troca(factory):
    async with factory() as session:
        contexto = await carregar_contexto(session, "conv-vazia")

    assert contexto.ultima_troca is None


async def test_obter_contexto_conversa_anterior_com_resumo(factory):
    async with factory() as session:
        await registrar_email(session, "conv-passada", "cliente@empresa.com")
        await registrar_troca(
            session, "conv-passada", "Quero 10 rádios", "Orçamento enviado", "vendas"
        )
        # Define um resumo na conversa passada
        from app.db.models import Conversa

        conversa = await session.get(Conversa, "conv-passada")
        conversa.resumo = "Cliente pediu cotação de 10 rádios e recebeu o orçamento."
        await session.commit()

        # Cria uma nova conversa do mesmo cliente
        await registrar_email(session, "conv-atual", "cliente@empresa.com")
        await registrar_troca(session, "conv-atual", "Olá", "Olá! Em que posso ajudar?", "vendas")

    async with factory() as session:
        contexto = await obter_contexto_conversa_anterior(
            session, email="cliente@empresa.com", conversa_atual_id="conv-atual"
        )

    assert contexto == "Cliente pediu cotação de 10 rádios e recebeu o orçamento."


async def test_obter_contexto_conversa_anterior_sem_resumo_formata_mensagens(factory):
    async with factory() as session:
        await registrar_email(session, "conv-sem-resumo", "ana@empresa.com")
        await registrar_troca(
            session,
            "conv-sem-resumo",
            "Preciso de suporte no GD-15",
            "Qual o erro apresentado?",
            "suporte",
        )

        await registrar_email(session, "conv-nova", "ana@empresa.com")

    async with factory() as session:
        contexto = await obter_contexto_conversa_anterior(
            session, email="ana@empresa.com", conversa_atual_id="conv-nova"
        )

    assert "Cliente: Preciso de suporte no GD-15" in contexto
    assert "Assistente: Qual o erro apresentado?" in contexto


async def test_obter_contexto_conversa_anterior_retorna_none_se_nao_houver_conversa_previa(factory):
    async with factory() as session:
        await registrar_email(session, "conv-unica", "novo@empresa.com")

    async with factory() as session:
        # Se só existe a conversa atual
        ctx1 = await obter_contexto_conversa_anterior(
            session, email="novo@empresa.com", conversa_atual_id="conv-unica"
        )
        # Se o e-mail nem existe no banco
        ctx2 = await obter_contexto_conversa_anterior(
            session, email="desconhecido@empresa.com", conversa_atual_id="qualquer"
        )

    assert ctx1 is None
    assert ctx2 is None


async def test_registrar_troca_reabre_conversa_encerrada(factory):
    # Achado da revisão de 2026-10-04: uma mensagem chegando numa conversa
    # já `status="encerrada"` ficava gravada sem reabri-la, corrompendo as
    # métricas por dia que bucketam pelo `encerrada_em` congelado.
    from datetime import UTC, datetime

    from app.db.models import Conversa

    async with factory() as session:
        conversa = Conversa(
            id="conv-encerrada",
            status="encerrada",
            encerrada_em=datetime(2026, 10, 1, 12, 0, tzinfo=UTC),
            motivo_encerramento="inatividade",
        )
        session.add(conversa)
        await session.commit()

    async with factory() as session:
        conversa_atualizada, _ = await registrar_troca(
            session, "conv-encerrada", "Ainda está aí?", "Sim, como posso ajudar?", "atendimento"
        )

    assert conversa_atualizada.status == "aberta"
    assert conversa_atualizada.encerrada_em is None
    assert conversa_atualizada.motivo_encerramento is None
