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


# --- ajustar_estoque: define a quantidade final (um produto ou todos) --------------------------


async def _produto(session, nome, estoques):
    p = await criar_produto(
        session, nome=nome, descricao="d", preco=Decimal("10"), categoria="Geral"
    )
    pid = p.id
    for cd, qtd in estoques.items():
        await atualizar_estoque(session, pid, cd, qtd)
    return pid


async def _saldo_ou_none(session, produto_id, cd):
    session.expire_all()
    p = await obter_produto(session, produto_id)
    return next((e.quantidade for e in p.estoques if e.centro_distribuicao == cd), None)


async def _propor_e_confirmar(session, args, admin_id=1):
    acao, previa = await criar_proposta(
        session, admin_id=admin_id, ferramenta="ajustar_estoque", argumentos=args
    )
    acao_id = acao.id
    await confirmar(session, acao_id, admin_id=admin_id)
    return previa


@pytest.mark.asyncio
async def test_ajustar_estoque_de_um_produto_define_a_quantidade_e_ignora_caixa_do_cd(db_session):
    pid = await _produto(db_session, "Leitor", {"CD-Matriz": 7})
    previa = await _propor_e_confirmar(
        db_session, {"produto": pid, "cd": "cd-matriz", "quantidade": 20}
    )
    assert previa.antes == {"CD-Matriz": 7} and previa.depois == {"CD-Matriz": 20}
    assert await _saldo_ou_none(db_session, pid, "CD-Matriz") == 20


@pytest.mark.asyncio
async def test_ajustar_estoque_cria_a_linha_quando_o_produto_nao_tem_estoque_no_cd(db_session):
    pid = await _produto(db_session, "Sem estoque", {})
    previa = await _propor_e_confirmar(
        db_session, {"produto": pid, "cd": "CD-MATRIZ", "quantidade": 20}
    )
    assert previa.antes == {"CD-Matriz": 0}
    assert await _saldo_ou_none(db_session, pid, "CD-Matriz") == 20


@pytest.mark.asyncio
async def test_ajustar_estoque_de_todos_os_produtos_so_aplica_ao_confirmar(db_session):
    a = await _produto(db_session, "A", {"CD-Matriz": 3, "CD-SP": 9})
    b = await _produto(db_session, "B", {})
    c = await _produto(db_session, "C", {"CD-Matriz": 50})
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="ajustar_estoque",
        argumentos={"todos": True, "cd": "CD-MATRIZ", "quantidade": 20},
    )
    acao_id = acao.id
    assert previa.antes["produtos afetados"] == 3
    assert previa.depois["quantidade em cada produto"] == 20
    assert await _saldo_ou_none(db_session, a, "CD-Matriz") == 3  # só a prévia
    await confirmar(db_session, acao_id, admin_id=1)
    for pid in (a, b, c):
        assert await _saldo_ou_none(db_session, pid, "CD-Matriz") == 20
    assert await _saldo_ou_none(db_session, a, "CD-SP") == 9  # outro CD intocado


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {"cd": "CD-Matriz", "quantidade": 20},  # nem produto nem todos
        {"produto": 1, "todos": True, "cd": "CD-Matriz", "quantidade": 20},  # os dois
        {"todos": True, "cd": "CD-Matriz", "quantidade": -1},
        {"todos": True, "cd": "CD-Matriz", "quantidade": 2.5},
        {"todos": True, "cd": "", "quantidade": 3},
    ],
)
async def test_ajustar_estoque_recusa_argumentos_invalidos(db_session, args):
    await _produto(db_session, "X", {})
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(db_session, admin_id=1, ferramenta="ajustar_estoque", argumentos=args)


@pytest.mark.asyncio
async def test_ajustar_estoque_aceita_zero(db_session):
    pid = await _produto(db_session, "Zerar", {"CD-Matriz": 5})
    await _propor_e_confirmar(db_session, {"produto": pid, "cd": "CD-Matriz", "quantidade": 0})
    assert await _saldo_ou_none(db_session, pid, "CD-Matriz") == 0
