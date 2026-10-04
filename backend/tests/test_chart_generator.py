from decimal import Decimal
import pytest
from app.db.models import (
    AdminChart,
    Cliente,
    ClienteCompra,
    Conversa,
    ConversaMensagem,
    Pedido,
    PedidoItem,
    Produto,
    ProdutoEstoque,
)
from app.services.chart_generator import (
    SUPPORTED_QUERIES,
    detect_chart_request,
    execute_chart_aggregation,
    generate_and_persist_chart,
)


def test_detect_chart_request():
    assert detect_chart_request("gere um gráfico de vendas por categoria") is not None
    res = detect_chart_request("mostre o estoque num gráfico de pizza")
    assert res is not None
    assert res["tipo_grafico"] == "pie"
    assert res["query_key"] == "estoque_por_cd"

    # Intenção solicitada pelo usuário: "gere grafico de venda de produtos x quantidade"
    res_qtd = detect_chart_request("gere grafico de venda de produtos x quantidade")
    assert res_qtd is not None
    assert res_qtd["query_key"] == "vendas_produtos_quantidade"
    assert res_qtd["titulo"] == "Vendas por Produto (Quantidade)"
    assert res_qtd["tipo_grafico"] == "bar"

    # Intenção por faturamento/valor
    res_val = detect_chart_request("gráfico de venda de produtos por faturamento")
    assert res_val is not None
    assert res_val["query_key"] == "vendas_produtos_valor"
    assert res_val["titulo"] == "Vendas por Produto (Faturamento)"

    # Categoria por quantidade
    res_cat_qtd = detect_chart_request("gráfico de quantidade por categoria")
    assert res_cat_qtd is not None
    assert res_cat_qtd["query_key"] == "vendas_categoria_quantidade"

    # Não deve disparar para perguntas comuns
    assert detect_chart_request("como trocar meu produto?") is None
    assert detect_chart_request("quero saber o preço do alicate") is None


@pytest.mark.asyncio
async def test_execute_chart_aggregation_vendas(db_session):
    p1 = Produto(
        nome="Chave Philips",
        descricao="Ferramenta manual",
        preco=Decimal("35.50"),
        categoria="Ferramentas",
    )
    p2 = Produto(
        nome="Cabo Coaxial",
        descricao="Material elétrico",
        preco=Decimal("120.00"),
        categoria="Elétrica",
    )
    db_session.add_all([p1, p2])
    await db_session.commit()

    config, data = await execute_chart_aggregation(db_session, "vendas_por_categoria")
    assert config["x_key"] == "categoria"
    assert "total" in config["y_keys"]
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_execute_chart_aggregation_estoque(db_session):
    p = Produto(nome="Item A", descricao="Desc", preco=Decimal("10.00"), categoria="Geral")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(p)

    e1 = ProdutoEstoque(produto_id=p.id, centro_distribuicao="CD São Paulo", quantidade=50)
    e2 = ProdutoEstoque(produto_id=p.id, centro_distribuicao="CD Curitiba", quantidade=25)
    db_session.add_all([e1, e2])
    await db_session.commit()

    config, data = await execute_chart_aggregation(db_session, "estoque_por_cd")
    assert config["x_key"] == "centro_distribuicao"
    assert len(data) == 2


@pytest.mark.asyncio
async def test_execute_chart_aggregation_pedidos(db_session):
    ped1 = Pedido(status="reservado")
    ped2 = Pedido(status="aprovado")
    ped3 = Pedido(status="reservado")
    db_session.add_all([ped1, ped2, ped3])
    await db_session.commit()

    config, data = await execute_chart_aggregation(db_session, "pedidos_por_status")
    assert config["x_key"] == "status"
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_execute_chart_aggregation_tokens(db_session):
    conv = Conversa(id="conv-1", status="encerrada")
    db_session.add(conv)
    msg1 = ConversaMensagem(
        conversa_id="conv-1",
        papel="assistente",
        texto="Olá!",
        dominio="atendimento",
        metricas={"prompt_tokens": 10, "completion_tokens": 20, "estimated_cost_usd": 0.001},
    )
    db_session.add(msg1)
    await db_session.commit()

    config, data = await execute_chart_aggregation(db_session, "metricas_tokens_por_dia")
    assert config["x_key"] == "data"
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_generate_and_persist_chart(db_session):
    chart = await generate_and_persist_chart(
        db_session,
        prompt="crie um gráfico de barras com os estoques por centro de distribuição",
        user_email="admin@empresa.com",
    )
    assert chart is not None
    assert isinstance(chart, AdminChart)
    assert chart.tipo_grafico == "bar"
    assert chart.criado_por == "admin@empresa.com"
    assert chart.sql_query == "estoque_por_cd"
    assert "x_key" in chart.config_json


@pytest.mark.asyncio
async def test_execute_chart_aggregation_produtos_quantidade(db_session):
    from datetime import UTC, datetime
    p1 = Produto(nome="Gerador X", descricao="Gerador", preco=Decimal("1000.00"), categoria="Geradores")
    p2 = Produto(nome="Gerador Y", descricao="Gerador", preco=Decimal("2000.00"), categoria="Geradores")
    db_session.add_all([p1, p2])
    await db_session.commit()
    await db_session.refresh(p1)
    await db_session.refresh(p2)

    cliente = Cliente(nome="Comprador", email="comprador@teste.com")
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)

    compra = ClienteCompra(
        cliente_id=cliente.id,
        produto_id=p1.id,
        quantidade=5,
        valor_total=Decimal("5000.00"),
        comprado_em=datetime.now(UTC),
    )
    db_session.add(compra)

    pedido = Pedido(status="reservado")
    db_session.add(pedido)
    await db_session.commit()
    await db_session.refresh(pedido)

    item = PedidoItem(
        pedido_id=pedido.id,
        produto_id=p2.id,
        centro_distribuicao="CD SP",
        quantidade=3,
        preco_unitario=Decimal("2000.00"),
    )
    db_session.add(item)
    await db_session.commit()

    config, dados = await execute_chart_aggregation(db_session, "vendas_produtos_quantidade")
    assert config["x_key"] == "produto"
    assert config["y_keys"] == ["quantidade"]
    assert config["format"] == "number"
    assert len(dados) == 2
    # Gerador X deve ter 5 unidades vendidas
    prod_x = next(d for d in dados if d["produto"] == "Gerador X")
    assert prod_x["quantidade"] == 5
    # Gerador Y deve ter 3 unidades
    prod_y = next(d for d in dados if d["produto"] == "Gerador Y")
    assert prod_y["quantidade"] == 3


@pytest.mark.asyncio
async def test_generate_and_persist_chart_produtos_quantidade(db_session):
    chart = await generate_and_persist_chart(
        db_session,
        prompt="gere grafico de venda de produtos x quantidade",
        user_email="admin@empresa.com",
    )
    assert chart is not None
    assert chart.sql_query == "vendas_produtos_quantidade"
    assert chart.config_json["format"] == "number"
    assert chart.config_json["y_keys"] == ["quantidade"]

