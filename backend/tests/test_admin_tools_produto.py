from decimal import Decimal

import pytest

from app.admin_tools import (
    ferramentas,
    ferramentas_produto,  # noqa: F401  (registra as ferramentas)
)
from app.admin_tools.ferramentas_produto import ProdutoAmbiguoError, resolver_produto
from app.admin_tools.propostas import PropostaInvalidaError, confirmar, criar_proposta
from app.db.catalog import criar_produto, listar_produtos, obter_produto


async def _produto(session, nome, **kw):
    return await criar_produto(
        session,
        nome=nome,
        descricao=kw.get("descricao", "d"),
        preco=Decimal("10"),
        categoria="Geral",
    )


@pytest.mark.asyncio
async def test_resolver_produto_por_id_nome_e_ambiguidade(db_session):
    a = await _produto(db_session, "Controlador iDFace Max")
    await _produto(db_session, "Controlador iDFace Mini")
    assert (await resolver_produto(db_session, a.id)).id == a.id
    assert (await resolver_produto(db_session, "iDFace Max")).id == a.id
    with pytest.raises(ProdutoAmbiguoError) as exc:
        await resolver_produto(db_session, "iDFace")
    assert len(exc.value.candidatos) == 2
    with pytest.raises(PropostaInvalidaError):
        await resolver_produto(db_session, "inexistente")
    with pytest.raises(PropostaInvalidaError):
        await resolver_produto(db_session, 999999)


@pytest.mark.asyncio
async def test_incluir_produto_so_grava_depois_de_confirmar(db_session):
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="incluir_produto",
        argumentos={"nome": "Novo", "descricao": "Desc", "preco": "99.90", "categoria": "CFTV"},
    )
    assert previa.depois["nome"] == "Novo"
    assert await listar_produtos(db_session, termo="Novo") == []
    await confirmar(db_session, acao.id, admin_id=1)
    achados = await listar_produtos(db_session, termo="Novo")
    assert len(achados) == 1 and achados[0].preco == Decimal("99.90")


@pytest.mark.asyncio
async def test_alterar_nome_e_descricao_mostram_antes_e_depois(db_session):
    p = await _produto(db_session, "Antigo", descricao="velha")
    acao, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="alterar_nome_produto",
        argumentos={"produto": p.id, "novo_nome": "Moderno"},
    )
    assert previa.antes == {"nome": "Antigo"} and previa.depois == {"nome": "Moderno"}
    await confirmar(db_session, acao.id, admin_id=1)
    assert (await obter_produto(db_session, p.id)).nome == "Moderno"

    acao2, previa2 = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="alterar_descricao_produto",
        argumentos={"produto": p.id, "nova_descricao": "nova"},
    )
    assert previa2.antes == {"descricao": "velha"}
    await confirmar(db_session, acao2.id, admin_id=1)
    assert (await obter_produto(db_session, p.id)).descricao == "nova"


@pytest.mark.asyncio
async def test_alterar_produto_ambiguo_nao_e_adivinhado(db_session):
    await _produto(db_session, "Sensor Alfa")
    await _produto(db_session, "Sensor Beta")
    with pytest.raises(ProdutoAmbiguoError):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="alterar_nome_produto",
            argumentos={"produto": "Sensor", "novo_nome": "X"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "args",
    [
        {"nome": "", "descricao": "d", "preco": "1", "categoria": "x"},
        {"nome": "n", "descricao": "d", "preco": "-1", "categoria": "x"},
        {"nome": "n", "descricao": "d", "preco": "abc", "categoria": "x"},
        {"nome": "n", "descricao": "d", "preco": "1"},
    ],
)
async def test_incluir_produto_rejeita_argumentos_invalidos(db_session, args):
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(db_session, admin_id=1, ferramenta="incluir_produto", argumentos=args)


@pytest.mark.asyncio
async def test_alterar_nome_rejeita_novo_nome_vazio(db_session):
    p = await _produto(db_session, "Fixo")
    with pytest.raises(PropostaInvalidaError):
        await criar_proposta(
            db_session,
            admin_id=1,
            ferramenta="alterar_nome_produto",
            argumentos={"produto": p.id, "novo_nome": "   "},
        )


@pytest.mark.asyncio
async def test_erro_em_executar_nao_deixa_produto_gravado(db_session, monkeypatch):
    acao, _ = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="incluir_produto",
        argumentos={"nome": "Falha", "descricao": "d", "preco": "5", "categoria": "x"},
    )
    impl = ferramentas.FERRAMENTAS["incluir_produto"]
    original = impl.executar

    async def _quebra(session, args, *, admin_id):
        await original(session, args, admin_id=admin_id)
        raise RuntimeError("falha depois de gravar")

    monkeypatch.setattr(impl, "executar", _quebra)
    with pytest.raises(RuntimeError):
        await confirmar(db_session, acao.id, admin_id=1)
    assert await listar_produtos(db_session, termo="Falha") == []


@pytest.mark.asyncio
async def test_resolver_produto_com_digito_unicode_nao_quebra(db_session):
    with pytest.raises(PropostaInvalidaError):
        await resolver_produto(db_session, "²")


@pytest.mark.asyncio
@pytest.mark.parametrize(("bruto", "esperado"), [("199,90", "199.90"), ("1.299,90", "1299.90")])
async def test_incluir_aceita_preco_com_virgula_e_previa_mostra_descricao(
    db_session, bruto, esperado
):
    _, previa = await criar_proposta(
        db_session,
        admin_id=1,
        ferramenta="incluir_produto",
        argumentos={"nome": "P", "descricao": "Desc X", "preco": bruto, "categoria": "c"},
    )
    assert previa.depois["preco"] == esperado
    assert previa.depois["descricao"] == "Desc X"
