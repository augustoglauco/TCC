"""Classificação do usuário (R10, Fase 6) — `app.user_profile.classificacao`."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, Cliente, ClienteCompra, Conversa
from app.memory.store import registrar_troca
from app.user_profile.classificacao import (
    PERFIL_CLIENTE,
    PERFIL_ESPORADICO,
    PERFIL_LEAD,
    PERFIL_NAO_CLASSIFICADO,
    atualizar_perfil,
    classificar,
    extrair_email,
)

AGORA = datetime(2026, 9, 25, tzinfo=UTC)


def _dias_atras(*dias: int) -> list[datetime]:
    return [AGORA - timedelta(days=d) for d in dias]


# --- Regra pura -----------------------------------------------------------------


def test_duas_ou_mais_compras_com_a_ultima_recente_e_cliente():
    c = classificar(_dias_atras(30, 200), tem_email=True, teve_intencao_compra=False, agora=AGORA)
    assert (c.perfil, c.motivo) == (PERFIL_CLIENTE, "2 compras, a última há 30 dias")


def test_uma_unica_compra_e_esporadico():
    c = classificar(_dias_atras(10), tem_email=True, teve_intencao_compra=True, agora=AGORA)
    assert c.perfil == PERFIL_ESPORADICO


def test_compras_antigas_sao_esporadico_mesmo_sendo_varias():
    c = classificar(_dias_atras(400, 700), tem_email=True, teve_intencao_compra=False, agora=AGORA)
    assert (c.perfil, c.motivo) == (PERFIL_ESPORADICO, "2 compras, a última há 400 dias")


def test_sem_cadastro_com_intencao_de_compra_e_lead():
    assert classificar(None, False, True, AGORA).perfil == PERFIL_LEAD
    c = classificar(None, True, True, AGORA)
    assert (c.perfil, c.motivo) == (PERFIL_LEAD, "intenção de compra, e-mail sem cadastro")


def test_sem_sinais_nao_classifica():
    assert classificar(None, False, False, AGORA).perfil == PERFIL_NAO_CLASSIFICADO
    assert classificar(None, True, False, AGORA).perfil == PERFIL_NAO_CLASSIFICADO


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("meu e-mail é Ana.Recorrente@Example.com, obrigado", "ana.recorrente@example.com"),
        ("contato: joao_silva+tcc@empresa.com.br.", "joao_silva+tcc@empresa.com.br"),
        ("não tenho e-mail aqui", None),
        ("arroba solta @ no meio", None),
    ],
)
def test_extrair_email(texto, esperado):
    assert extrair_email(texto) == esperado


# --- Com o banco ------------------------------------------------------------------


@pytest.fixture
async def factory():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        ana = Cliente(email="ana.recorrente@example.com", nome="Ana")
        bruno = Cliente(email="bruno.unico@example.com", nome="Bruno")
        session.add_all([ana, bruno])
        await session.flush()
        session.add_all(
            [
                ClienteCompra(
                    cliente_id=ana.id,
                    quantidade=1,
                    valor_total=Decimal("100"),
                    comprado_em=AGORA - timedelta(days=d),
                )
                for d in (30, 90, 200)
            ]
            + [
                ClienteCompra(
                    cliente_id=bruno.id,
                    quantidade=1,
                    valor_total=Decimal("100"),
                    comprado_em=AGORA - timedelta(days=60),
                )
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()


async def _troca_e_perfil(factory, conversa: str, mensagem: str, dominio: str):
    async with factory() as session:
        await registrar_troca(session, conversa, mensagem, "resposta", dominio)
        return await atualizar_perfil(session, conversa, mensagem, agora=AGORA)


async def test_email_de_cliente_recorrente_no_pos_venda(factory):
    c = await _troca_e_perfil(
        factory, "conv-p1", "Meu gerador parou. E-mail: ana.recorrente@example.com", "suporte"
    )

    assert c.perfil == PERFIL_CLIENTE
    async with factory() as session:
        conversa = await session.get(Conversa, "conv-p1")
    assert (conversa.email, conversa.perfil) == ("ana.recorrente@example.com", PERFIL_CLIENTE)


async def test_email_de_cliente_com_uma_compra(factory):
    c = await _troca_e_perfil(factory, "conv-p2", "bruno.unico@example.com", "atendimento")

    assert c.perfil == PERFIL_ESPORADICO


async def test_sem_email_com_intencao_de_compra_vira_lead(factory):
    c = await _troca_e_perfil(factory, "conv-p3", "Quanto custa o GD-15?", "vendas")

    assert (c.perfil, c.motivo) == (PERFIL_LEAD, "intenção de compra")


async def test_email_fica_lembrado_nas_mensagens_seguintes(factory):
    await _troca_e_perfil(factory, "conv-p4", "Sou ana.recorrente@example.com", "suporte")

    c = await _troca_e_perfil(factory, "conv-p4", "E o manual do QTA-100?", "suporte")

    assert c.perfil == PERFIL_CLIENTE


async def test_email_sem_cadastro_e_sem_intencao_nao_classifica(factory):
    c = await _troca_e_perfil(
        factory, "conv-p5", "fulano@example.org, minha nota fiscal", "atendimento"
    )

    assert c.perfil == PERFIL_NAO_CLASSIFICADO
