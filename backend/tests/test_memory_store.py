"""Memória da conversa no Postgres (R9, Fase 6) — `app.memory.store`."""

import pytest

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.memory.store import (
    carregar_contexto,
    contar_mensagens,
    listar_mensagens,
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
