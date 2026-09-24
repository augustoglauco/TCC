"""Testes do backend único de catálogo/estoque/preços (R12, Fase 5) — ver
app.db.catalog. Cobre o CRUD básico sobre SQLite em memória (mesmo padrão de
test_rag_registry.py/test_tom_escalonamentos_api.py).
"""

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.db.catalog import (
    EstoqueInsuficienteError,
    ProdutoInexistenteError,
    adicionar_desconto_volume,
    atualizar_estoque,
    atualizar_produto,
    calcular_item_cotacao,
    criar_compatibilidade,
    criar_pedido,
    criar_produto,
    deletar_produto,
    listar_descontos_volume,
    listar_estoque,
    listar_produtos,
    obter_produto,
    preco_vigente,
    sao_compativeis,
)
from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base


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


async def test_deletar_produto_remove_compatibilidades_e_itens_de_pedido_associados(db_session):
    """Achado no code-review (2026-09-24): as tabelas novas da ferramenta
    MCP B2B (compatibilidade, pedido/reserva) não têm ondelete=CASCADE nem
    relationship cascade a partir de Produto — sem os DELETEs explícitos em
    deletar_produto, isso levantaria IntegrityError no Postgres real."""
    produto = await _cria_produto(db_session, nome="Principal")
    outro = await _cria_produto(db_session, nome="Compatível")
    await criar_compatibilidade(db_session, produto.id, outro.id)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 10)
    await criar_pedido(db_session, [(produto.id, 2, "CD-SP")])

    await deletar_produto(db_session, produto.id)

    assert await sao_compativeis(db_session, produto.id, outro.id) is False


# --- Ferramenta 1: validação de compatibilidade -----------------------------


async def test_sao_compativeis_reconhece_o_par_cadastrado(db_session):
    a = await _cria_produto(db_session, nome="A")
    b = await _cria_produto(db_session, nome="B")
    await criar_compatibilidade(db_session, a.id, b.id)

    assert await sao_compativeis(db_session, a.id, b.id) is True


async def test_sao_compativeis_e_simetrico_mesmo_sem_linha_invertida(db_session):
    a = await _cria_produto(db_session, nome="A")
    b = await _cria_produto(db_session, nome="B")
    await criar_compatibilidade(db_session, a.id, b.id)

    # Só existe a linha A -> B, não B -> A — a consulta cobre os dois
    # sentidos sem duplicar a escrita (ver docstring de ProdutoCompatibilidade).
    assert await sao_compativeis(db_session, b.id, a.id) is True


async def test_sao_compativeis_retorna_falso_para_par_nao_cadastrado(db_session):
    a = await _cria_produto(db_session, nome="A")
    b = await _cria_produto(db_session, nome="B")

    assert await sao_compativeis(db_session, a.id, b.id) is False


# --- Ferramenta 3: cotação automática ---------------------------------------


async def test_preco_vigente_usa_promocional_quando_ainda_nao_venceu(db_session):
    produto = await _cria_produto(
        db_session,
        preco_promocional=Decimal("19900.00"),
        promocao_valida_ate=datetime(2030, 1, 1, tzinfo=UTC),
    )

    preco = preco_vigente(produto, agora=datetime(2026, 1, 1, tzinfo=UTC))

    assert preco == Decimal("19900.00")


async def test_preco_vigente_ignora_promocional_vencida(db_session):
    produto = await _cria_produto(
        db_session,
        preco_promocional=Decimal("19900.00"),
        promocao_valida_ate=datetime(2020, 1, 1, tzinfo=UTC),
    )

    preco = preco_vigente(produto, agora=datetime(2026, 1, 1, tzinfo=UTC))

    assert preco == Decimal("24900.00")


async def test_preco_vigente_ignora_promocional_sem_data_de_validade(db_session):
    # promocao_valida_ate=None conta como "sem campanha vigente", mesmo com
    # preco_promocional preenchido (ver docstring de preco_vigente).
    produto = await _cria_produto(db_session, preco_promocional=Decimal("19900.00"))

    assert preco_vigente(produto) == Decimal("24900.00")


async def test_calcular_item_cotacao_sem_faixa_atingida_nao_aplica_desconto(db_session):
    produto = await _cria_produto(db_session)
    produto_id = produto.id
    await adicionar_desconto_volume(db_session, produto_id, 5, Decimal("5.00"))
    # `produto` já está na identity map da sessão com `descontos_volume`
    # carregado (vazio, desde a criação) — sem `expire_all()`, uma nova
    # query com selectinload não sobrescreve a coleção já em memória. `id`
    # é capturado antes do `expire_all()` porque acessar um atributo
    # expirado fora do contexto async do SQLAlchemy levanta `MissingGreenlet`.
    db_session.expire_all()
    produto = await obter_produto(db_session, produto_id)

    preco_unitario, percentual, subtotal = calcular_item_cotacao(produto, 3)

    assert preco_unitario == Decimal("24900.00")
    assert percentual == Decimal("0")
    assert subtotal == Decimal("74700.00")


async def test_calcular_item_cotacao_aplica_a_maior_faixa_atingida(db_session):
    produto = await _cria_produto(db_session)
    produto_id = produto.id
    await adicionar_desconto_volume(db_session, produto_id, 5, Decimal("5.00"))
    await adicionar_desconto_volume(db_session, produto_id, 10, Decimal("10.00"))
    db_session.expire_all()
    produto = await obter_produto(db_session, produto_id)

    preco_unitario, percentual, subtotal = calcular_item_cotacao(produto, 12)

    assert preco_unitario == Decimal("24900.00")
    assert percentual == Decimal("10.00")
    assert subtotal == Decimal("24900.00") * Decimal("0.90") * 12


# --- Ferramenta 4: reserva/pedido -------------------------------------------


async def test_criar_pedido_decrementa_estoque_e_grava_preco_unitario(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 10)

    pedido = await criar_pedido(db_session, [(produto.id, 3, "CD-SP")])

    assert pedido.status == "reservado"
    [item] = pedido.itens
    assert item.produto_id == produto.id
    assert item.quantidade == 3
    assert item.centro_distribuicao == "CD-SP"
    assert item.preco_unitario == Decimal("24900.00")
    estoques = await listar_estoque(db_session, produto.id)
    assert estoques[0].quantidade == 7


async def test_criar_pedido_com_estoque_insuficiente_nao_grava_nada(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 2)

    with pytest.raises(EstoqueInsuficienteError):
        await criar_pedido(db_session, [(produto.id, 3, "CD-SP")])

    estoques = await listar_estoque(db_session, produto.id)
    assert estoques[0].quantidade == 2


async def test_criar_pedido_com_produto_inexistente_levanta_erro(db_session):
    with pytest.raises(ProdutoInexistenteError):
        await criar_pedido(db_session, [(999, 1, "CD-SP")])


async def test_criar_pedido_com_quantidade_negativa_levanta_value_error(db_session):
    """Achado no code-review (2026-09-24): a validação `Field(gt=0)` só
    existe no schema Pydantic da ferramenta MCP — `criar_pedido` é
    reaproveitável por qualquer chamador e precisa da própria guarda, senão
    uma quantidade negativa passa a checagem de disponibilidade (negativo
    nunca é "maior que" o disponível) e AUMENTA o estoque em vez de falhar."""
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 10)

    with pytest.raises(ValueError, match="Quantidade inválida"):
        await criar_pedido(db_session, [(produto.id, -1, "CD-SP")])

    estoques = await listar_estoque(db_session, produto.id)
    assert estoques[0].quantidade == 10


async def test_criar_pedido_com_quantidade_zero_levanta_value_error_nao_assertion(db_session):
    """Achado no code-review (2026-09-24): quantidade=0 para um produto sem
    nenhuma linha de estoque (`estoque is None`, `disponivel=0`) passava a
    checagem antiga (`0 > 0` é falso) e só quebrava depois, com um
    `AssertionError` cru no loop de escrita, em vez do erro documentado."""
    produto = await _cria_produto(db_session)

    with pytest.raises(ValueError, match="Quantidade inválida"):
        await criar_pedido(db_session, [(produto.id, 0, "CD-SP")])


async def test_criar_pedido_falha_de_um_item_nao_decrementa_os_demais(db_session):
    """Vários itens no mesmo pedido: se um item não tem estoque, nenhum item
    é decrementado — mesmo os que tinham estoque suficiente (decisão de
    implementação documentada em `criar_pedido`)."""
    produto_ok = await _cria_produto(db_session, nome="OK")
    produto_sem_estoque = await _cria_produto(db_session, nome="Sem estoque")
    await atualizar_estoque(db_session, produto_ok.id, "CD-SP", 10)
    await atualizar_estoque(db_session, produto_sem_estoque.id, "CD-SP", 1)

    with pytest.raises(EstoqueInsuficienteError):
        await criar_pedido(
            db_session,
            [(produto_ok.id, 2, "CD-SP"), (produto_sem_estoque.id, 5, "CD-SP")],
        )

    estoques_ok = await listar_estoque(db_session, produto_ok.id)
    assert estoques_ok[0].quantidade == 10


async def test_criar_pedido_soma_itens_duplicados_do_mesmo_par_antes_de_validar(db_session):
    """Achado no security-review (2026-09-24): dois itens separados na
    mesma chamada, para o mesmo (produto, centro_distribuicao), eram
    validados cada um isoladamente contra o mesmo `disponivel` — dois itens
    de 6 unidades passavam individualmente (6 < 10) contra um estoque de
    10, e o estoque final ficava negativo (10 - 6 - 6 = -2). A soma das
    quantidades pedidas para o mesmo par deve ser validada, não cada
    ocorrência isolada."""
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 10)

    with pytest.raises(EstoqueInsuficienteError):
        await criar_pedido(
            db_session,
            [(produto.id, 6, "CD-SP"), (produto.id, 6, "CD-SP")],
        )

    estoques = await listar_estoque(db_session, produto.id)
    assert estoques[0].quantidade == 10


async def test_criar_pedido_aceita_itens_duplicados_quando_a_soma_cabe_no_estoque(db_session):
    produto = await _cria_produto(db_session)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 10)

    pedido = await criar_pedido(
        db_session,
        [(produto.id, 4, "CD-SP"), (produto.id, 4, "CD-SP")],
    )

    assert len(pedido.itens) == 2
    estoques = await listar_estoque(db_session, produto.id)
    assert estoques[0].quantidade == 2


async def test_criar_pedido_sob_concorrencia_pode_sobre_reservar():
    """Documenta (não corrige) a limitação de MVP registrada em
    `docs/ARCHITECTURE.md` §6 ("Governança e segurança") e no docstring de
    `criar_pedido`: sem lock otimista/pessimista, duas chamadas concorrentes
    a `criar_pedido` para o mesmo produto/centro podem ler o mesmo estoque
    "disponível" antes de qualquer uma escrever, e as duas decrementam —
    sobre-reservando (aqui, 2x3 unidades reservadas de um estoque de 5).
    Usa sessões independentes (mesmo padrão de app.mcp_server.b2b, uma
    `async with session_factory()` por chamada) para simular duas requisições
    concorrentes de verdade, não o mesmo `AsyncSession` compartilhado
    (`db_session`) que o resto deste arquivo usa."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    async with factory() as session:
        produto = await _cria_produto(session)
        await atualizar_estoque(session, produto.id, "CD-SP", 5)
    produto_id = produto.id

    async def _reservar() -> str:
        async with factory() as session:
            try:
                await criar_pedido(session, [(produto_id, 3, "CD-SP")])
                return "ok"
            except EstoqueInsuficienteError:
                return "falhou"

    resultados = await asyncio.gather(_reservar(), _reservar())

    async with factory() as session:
        estoques = await listar_estoque(session, produto_id)

    # As duas chamadas conseguem reservar (nenhum lock impede a segunda de
    # ler o estoque "5" antes da primeira commitar) — cada uma calcula
    # independentemente 5 - 3 = 2 a partir da mesma leitura inicial e grava
    # esse valor (não um decremento atômico no banco); a última a commitar
    # "vence" (lost update). Resultado: dois pedidos de 3 unidades cada
    # (6 no total, mais que as 5 disponíveis) foram criados com sucesso, mas
    # o estoque final mostra 2 — nem reflete a soma correta (-1) nem o
    # decremento de uma única reserva (2 já seria o valor "certo" para SÓ
    # uma delas). Ilustrativo da limitação aceita, não um comportamento
    # desejável a preservar se tratamento de concorrência for implementado
    # no futuro.
    assert resultados == ["ok", "ok"]
    assert estoques[0].quantidade == 2
    await engine.dispose()
