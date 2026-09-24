"""Testes do backend único de catálogo/estoque/preços (R12, Fase 5) — ver
app.db.catalog. Cobre o CRUD básico sobre SQLite em memória (mesmo padrão de
test_rag_registry.py/test_tom_escalonamentos_api.py).
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.db.catalog import (
    adicionar_desconto_volume,
    atualizar_estoque,
    atualizar_produto,
    criar_produto,
    deletar_produto,
    listar_descontos_volume,
    listar_estoque,
    listar_produtos,
    obter_produto,
)


async def _cria_produto(session, **overrides):
    defaults = dict(
        nome="Gerador Diesel GD-15",
        descricao="Potência de 15 kVA.",
        preco=Decimal("24900.00"),
        categoria="geradores",
    )
    defaults.update(overrides)
    return await criar_produto(session, **defaults)


async def test_criar_produto_grava_e_devolve_o_produto_criado(db_session):
    produto = await _cria_produto(db_session)

    assert produto.id is not None
    assert produto.nome == "Gerador Diesel GD-15"
    assert produto.preco == Decimal("24900.00")
    assert produto.estoques == []
    assert produto.descontos_volume == []


async def test_criar_produto_aceita_promocao_valida_ate(db_session):
    # Achado no code-review (2026-09-24): criar_produto() não tinha esse
    # parâmetro, apesar de existir em Produto (ORM) e ProdutoCreate
    # (schema) — a convenção de chamada documentada
    # (criar_produto(session, **ProdutoCreate(...).model_dump())) quebrava
    # com TypeError, ou perdia a validade da promoção silenciosamente.
    validade = datetime(2026, 12, 31, tzinfo=UTC)

    produto = await _cria_produto(
        db_session,
        preco_promocional=Decimal("19900.00"),
        promocao_valida_ate=validade,
    )

    assert produto.preco_promocional == Decimal("19900.00")
    assert produto.promocao_valida_ate == validade


async def test_obter_produto_existente(db_session):
    criado = await _cria_produto(db_session)

    produto = await obter_produto(db_session, criado.id)

    assert produto is not None
    assert produto.id == criado.id


async def test_obter_produto_inexistente_retorna_none(db_session):
    assert await obter_produto(db_session, 999) is None


async def test_listar_produtos_retorna_todos_ordenados_por_id(db_session):
    primeiro = await _cria_produto(db_session, nome="Gerador A")
    segundo = await _cria_produto(db_session, nome="Gerador B")

    produtos = await listar_produtos(db_session)

    assert [p.id for p in produtos] == [primeiro.id, segundo.id]


async def test_listar_produtos_filtra_por_categoria(db_session):
    await _cria_produto(db_session, nome="Gerador A", categoria="geradores")
    await _cria_produto(db_session, nome="Cabine", categoria="acessórios")

    produtos = await listar_produtos(db_session, categoria="acessórios")

    assert [p.nome for p in produtos] == ["Cabine"]


async def test_atualizar_produto_altera_so_os_campos_enviados(db_session):
    produto = await _cria_produto(db_session)

    atualizado = await atualizar_produto(db_session, produto.id, {"preco": Decimal("22900.00")})

    assert atualizado is not None
    assert atualizado.preco == Decimal("22900.00")
    assert atualizado.nome == "Gerador Diesel GD-15"  # não mudou


async def test_atualizar_produto_aceita_limpar_campo_com_none(db_session):
    produto = await _cria_produto(db_session, preco_promocional=Decimal("19900.00"))

    atualizado = await atualizar_produto(db_session, produto.id, {"preco_promocional": None})

    assert atualizado is not None
    assert atualizado.preco_promocional is None


async def test_atualizar_produto_inexistente_retorna_none(db_session):
    assert await atualizar_produto(db_session, 999, {"preco": Decimal("1.00")}) is None


async def test_deletar_produto_existente_remove_e_retorna_true(db_session):
    produto = await _cria_produto(db_session)

    removido = await deletar_produto(db_session, produto.id)

    assert removido is True
    assert await obter_produto(db_session, produto.id) is None


async def test_deletar_produto_inexistente_retorna_false(db_session):
    assert await deletar_produto(db_session, 999) is False


async def test_atualizar_estoque_cria_linha_quando_nao_existe(db_session):
    produto = await _cria_produto(db_session)

    estoque = await atualizar_estoque(db_session, produto.id, "CD-SP", 12)

    assert estoque.produto_id == produto.id
    assert estoque.centro_distribuicao == "CD-SP"
    assert estoque.quantidade == 12


async def test_atualizar_estoque_faz_upsert_na_mesma_linha(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 12)

    await atualizar_estoque(db_session, produto.id, "CD-SP", 7)

    estoques = await listar_estoque(db_session, produto.id)
    assert len(estoques) == 1
    assert estoques[0].quantidade == 7


async def test_listar_estoque_agrupa_varios_centros_de_distribuicao(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 12)
    await atualizar_estoque(db_session, produto.id, "CD-RJ", 5)

    estoques = await listar_estoque(db_session, produto.id)

    assert {e.centro_distribuicao: e.quantidade for e in estoques} == {
        "CD-SP": 12,
        "CD-RJ": 5,
    }


async def test_adicionar_desconto_volume_e_listar(db_session):
    produto = await _cria_produto(db_session)

    await adicionar_desconto_volume(db_session, produto.id, 5, Decimal("5.00"))
    await adicionar_desconto_volume(db_session, produto.id, 10, Decimal("10.00"))

    descontos = await listar_descontos_volume(db_session, produto.id)

    assert [(d.quantidade_minima, d.percentual_desconto) for d in descontos] == [
        (5, Decimal("5.00")),
        (10, Decimal("10.00")),
    ]


async def test_deletar_produto_remove_estoque_e_descontos_associados(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 12)
    await adicionar_desconto_volume(db_session, produto.id, 5, Decimal("5.00"))

    await deletar_produto(db_session, produto.id)

    assert await listar_estoque(db_session, produto.id) == []
    assert await listar_descontos_volume(db_session, produto.id) == []
