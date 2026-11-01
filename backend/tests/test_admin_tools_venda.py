import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import update

from app.admin_tools import (  # noqa: F401
    ferramentas_estoque,
    ferramentas_produto,
    ferramentas_venda,
)
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import (
    atualizar_estoque,
    criar_pedido,
    criar_produto,
    obter_pedido,
    obter_produto,
)
from app.db.models import Pedido


async def _produto(session, nome, saldos):
    p = await criar_produto(
        session, nome=nome, descricao="d", preco=Decimal("10"), categoria="Geral"
    )
    for cd, saldo in saldos.items():
        await atualizar_estoque(session, p.id, cd, saldo)
    return p


async def _pedido_reservado(session, quantidade=3, saldo=10):
    p = await _produto(session, "Leitor", {"CD Sul": saldo})
    pedido = await criar_pedido(session, [(p.id, quantidade, "CD Sul")], user_email="c@x.com")
    return SimpleNamespace(id=p.id), SimpleNamespace(id=pedido.id)


async def _saldo(session, produto_id, cd="CD Sul"):
    session.expire_all()
    p = await obter_produto(session, produto_id)
    return next(e.quantidade for e in p.estoques if e.centro_distribuicao == cd)


def _args(pedido, novo):
    return {"pedido_id": str(pedido.id), "novo_status": novo}


async def _propor(session, pedido, novo):
    return await criar_proposta(
        session, admin_id=1, ferramenta="atualizar_venda", argumentos=_args(pedido, novo)
    )


@pytest.mark.asyncio
async def test_concluir_venda_preenche_conversao_e_nao_mexe_no_estoque(db_session):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    assert await _saldo(db_session, p.id) == 7
    acao, previa = await _propor(db_session, pedido, "venda_concluida")
    assert previa.antes == {"status": "reservado"}
    assert previa.depois == {"status": "venda_concluida"}
    await confirmar(db_session, acao.id, admin_id=1)
    db_session.expire_all()
    novo = await obter_pedido(db_session, pedido.id)
    assert novo.status == "venda_concluida" and novo.tipo_conversao == "chat_admin"
    assert novo.convertido_em is not None and novo.convertido_por == "admin:1"
    assert await _saldo(db_session, p.id) == 7


@pytest.mark.asyncio
async def test_cancelar_devolve_cada_item_ao_estoque_do_proprio_cd(db_session):
    a = await _produto(db_session, "A", {"CD Sul": 10, "CD Norte": 10})
    b = await _produto(db_session, "B", {"CD Sul": 5})
    pedido = await criar_pedido(
        db_session, [(a.id, 3, "CD Sul"), (a.id, 2, "CD Norte"), (b.id, 4, "CD Sul")]
    )
    pedido = SimpleNamespace(id=pedido.id)
    a, b = SimpleNamespace(id=a.id), SimpleNamespace(id=b.id)
    assert await _saldo(db_session, a.id) == 7
    assert await _saldo(db_session, a.id, "CD Norte") == 8
    assert await _saldo(db_session, b.id) == 1
    acao, previa = await _propor(db_session, pedido, "cancelada")
    assert previa.depois == {
        "status": "cancelada",
        "estoque_devolvido": {"CD Sul": 7, "CD Norte": 2},
    }
    await confirmar(db_session, acao.id, admin_id=1)
    db_session.expire_all()
    assert (await obter_pedido(db_session, pedido.id)).status == "cancelada"
    assert await _saldo(db_session, a.id) == 10
    assert await _saldo(db_session, a.id, "CD Norte") == 10
    assert await _saldo(db_session, b.id) == 5


@pytest.mark.asyncio
async def test_cancelar_venda_concluida_avisa_na_previa(db_session):
    _, pedido = await _pedido_reservado(db_session)
    a, _ = await _propor(db_session, pedido, "venda_concluida")
    await confirmar(db_session, a.id, admin_id=1)
    _, previa = await _propor(db_session, pedido, "cancelada")
    assert previa.aviso and "concluída" in previa.aviso


@pytest.mark.asyncio
async def test_pagamento_divergente_pode_concluir_ou_cancelar(db_session):
    _, pedido = await _pedido_reservado(db_session)
    (await obter_pedido(db_session, pedido.id)).status = "pagamento_divergente"
    await db_session.commit()
    for novo in ("venda_concluida", "cancelada"):
        _, previa = await _propor(db_session, pedido, novo)
        assert previa.antes == {"status": "pagamento_divergente"}


@pytest.mark.asyncio
async def test_cancelada_e_terminal_e_entradas_invalidas_falham(db_session):
    p, pedido = await _pedido_reservado(db_session)
    a, _ = await _propor(db_session, pedido, "cancelada")
    await confirmar(db_session, a.id, admin_id=1)
    for novo in ("venda_concluida", "cancelada"):
        with pytest.raises(PropostaInvalidaError):
            await _propor(db_session, pedido, novo)
    assert await _saldo(db_session, p.id) == 10
    for args in (
        {"pedido_id": str(pedido.id), "novo_status": "inventado"},
        {"pedido_id": str(uuid.uuid4()), "novo_status": "cancelada"},
        {"pedido_id": "nao-e-uuid", "novo_status": "cancelada"},
    ):
        with pytest.raises(PropostaInvalidaError):
            await criar_proposta(
                db_session, admin_id=1, ferramenta="atualizar_venda", argumentos=args
            )


@pytest.mark.asyncio
async def test_cancelar_duas_vezes_nao_devolve_estoque_duas_vezes(db_session):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    a1, _ = await _propor(db_session, pedido, "cancelada")
    a2, _ = await _propor(db_session, pedido, "cancelada")
    await confirmar(db_session, a1.id, admin_id=1)
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, a2.id, admin_id=1)
    assert await _saldo(db_session, p.id) == 10


@pytest.mark.asyncio
async def test_executar_repetido_apos_commit_recusa_pela_transicao(db_session):
    """Depois do commit o pedido é relido como `cancelada`: a checagem de transição recusa."""
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    impl = ferramentas_venda.AtualizarVenda()
    args = _args(pedido, "cancelada")
    await impl.executar(db_session, args, admin_id=1)
    await db_session.commit()
    with pytest.raises(PropostaInvalidaError):
        await impl.executar(db_session, args, admin_id=1)
    await db_session.rollback()
    assert await _saldo(db_session, p.id) == 10


@pytest.mark.asyncio
async def test_claim_atomico_recusa_pedido_obsoleto_e_nao_devolve_estoque(db_session):
    """Pedido lido como `reservado`, mas outro UPDATE já o cancelou: o WHERE do claim recusa."""
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    obsoleto = await obter_pedido(db_session, pedido.id)
    assert obsoleto.status == "reservado"
    await db_session.execute(
        update(Pedido)
        .where(Pedido.id == pedido.id)
        .values(status="cancelada")
        .execution_options(synchronize_session=False)
    )
    with pytest.raises(PropostaInvalidaError):
        await ferramentas_venda._reivindicar_status(db_session, obsoleto, "cancelada", 1)
    await db_session.rollback()
    assert await _saldo(db_session, p.id) == 7  # nada foi devolvido


@pytest.mark.asyncio
async def test_executar_com_pedido_obsoleto_nao_devolve_estoque(db_session, monkeypatch):
    p, pedido = await _pedido_reservado(db_session, quantidade=3, saldo=10)
    obsoleto = await obter_pedido(db_session, pedido.id)
    await db_session.execute(
        update(Pedido)
        .where(Pedido.id == pedido.id)
        .values(status="cancelada")
        .execution_options(synchronize_session=False)
    )

    async def _velho(session, args):
        return obsoleto, "cancelada"

    monkeypatch.setattr(ferramentas_venda, "_pedido_para_mudar", _velho)
    with pytest.raises(PropostaInvalidaError):
        await ferramentas_venda.AtualizarVenda().executar(
            db_session, _args(pedido, "cancelada"), admin_id=1
        )
    await db_session.rollback()
    assert await _saldo(db_session, p.id) == 7


@pytest.mark.asyncio
async def test_cancelar_venda_concluida_limpa_a_conversao(db_session):
    _, pedido = await _pedido_reservado(db_session)
    for novo in ("venda_concluida", "cancelada"):
        a, _ = await _propor(db_session, pedido, novo)
        await confirmar(db_session, a.id, admin_id=1)
    db_session.expire_all()
    final = await obter_pedido(db_session, pedido.id)
    assert final.status == "cancelada"
    assert final.tipo_conversao is None
    assert final.convertido_em is None and final.convertido_por is None
