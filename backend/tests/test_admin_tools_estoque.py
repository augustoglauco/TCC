from decimal import Decimal

import pytest

from app.admin_tools import ferramentas_estoque, ferramentas_produto  # noqa: F401
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import (
    EstoqueInsuficienteError,
    atualizar_estoque,
    baixar_estoque_atomico,
    criar_produto,
    devolver_estoque,
    obter_produto,
)


async def _com_estoque(session, saldo=40):
    p = await criar_produto(
        session, nome="Leitor", descricao="d", preco=Decimal("10"), categoria="Geral"
    )
    await atualizar_estoque(session, p.id, "CD Sul", saldo)
    return p


async def _saldo(session, produto_id, cd="CD Sul"):
    session.expire_all()
    p = await obter_produto(session, produto_id)
    return next(e.quantidade for e in p.estoques if e.centro_distribuicao == cd)


@pytest.mark.asyncio
async def test_baixar_estoque_atomico_subtrai_e_recusa_saldo_insuficiente(db_session):
    p = await _com_estoque(db_session, 40)
    assert await baixar_estoque_atomico(db_session, p.id, "CD Sul", 5) == 35
    with pytest.raises(EstoqueInsuficienteError):
        await baixar_estoque_atomico(db_session, p.id, "CD Sul", 36)
    await db_session.commit()
    assert await _saldo(db_session, p.id) == 35


@pytest.mark.asyncio
async def test_devolver_estoque_soma_e_cria_linha_se_nao_existir(db_session):
    p = await _com_estoque(db_session, 10)
    await devolver_estoque(db_session, p.id, "CD Sul", 4)
    await devolver_estoque(db_session, p.id, "CD Norte", 3)
    await db_session.commit()
    assert await _saldo(db_session, p.id) == 14 and await _saldo(db_session, p.id, "CD Norte") == 3


@pytest.mark.asyncio
async def test_baixa_estoque_mostra_antes_depois_e_so_aplica_ao_confirmar(db_session):
    p = await _com_estoque(db_session, 40)
    pid = p.id  # commit expira p; ler o id depois exigiria IO síncrona
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="baixa_estoque",
        argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 5},
    )
    acao_id = acao.id  # _saldo expira a sessão; ler o id depois exigiria IO síncrona
    assert previa.antes == {"CD Sul": 40} and previa.depois == {"CD Sul": 35}
    assert await _saldo(db_session, pid) == 40
    await confirmar(db_session, acao_id, admin_id=1)
    assert await _saldo(db_session, pid) == 35


@pytest.mark.asyncio
@pytest.mark.parametrize("quantidade", [0, -3, "abc", 2.5])
async def test_baixa_estoque_rejeita_quantidade_invalida(db_session, quantidade):
    p = await _com_estoque(db_session, 40)
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="baixa_estoque",
            argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": quantidade},
        )


@pytest.mark.asyncio
async def test_baixa_maior_que_o_saldo_e_recusada_ja_na_previa(db_session):
    p = await _com_estoque(db_session, 3)
    with pytest.raises(PropostaInvalidaError, match="Estoque insuficiente"):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="baixa_estoque",
            argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 5},
        )


@pytest.mark.asyncio
async def test_baixa_em_cd_sem_estoque_e_recusada(db_session):
    p = await _com_estoque(db_session, 3)
    with pytest.raises(PropostaInvalidaError, match="não tem estoque"):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="baixa_estoque",
            argumentos={"produto": p.id, "cd": "CD Norte", "quantidade": 1},
        )


@pytest.mark.asyncio
async def test_saldo_mudou_entre_a_previa_e_a_confirmacao_nao_deixa_negativo(db_session):
    p = await _com_estoque(db_session, 10)
    pid = p.id
    acao, _ = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="baixa_estoque",
        argumentos={"produto": p.id, "cd": "CD Sul", "quantidade": 8},
    )
    await baixar_estoque_atomico(db_session, pid, "CD Sul", 5)  # outra baixa concorrente
    await db_session.commit()
    with pytest.raises(PropostaInvalidaError):
        await confirmar(db_session, acao.id, admin_id=1)
    assert await _saldo(db_session, pid) == 5


@pytest.mark.asyncio
async def test_executar_traduz_corrida_em_proposta_invalida(db_session):
    # Segunda barreira: executar() direto (sem preparar) com saldo insuficiente.
    p = await _com_estoque(db_session, 2)
    ferramenta = ferramentas_estoque.BaixaEstoque()
    with pytest.raises(PropostaInvalidaError, match="Estoque insuficiente"):
        await ferramenta.executar(
            db_session, {"produto": p.id, "cd": "CD Sul", "quantidade": 9}, admin_id=1
        )
    assert await _saldo(db_session, p.id) == 2
