from decimal import Decimal
import pytest
from app.db.models import AdminChart, Conversa, ConversaMensagem, Pedido, Produto, ProdutoEstoque
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
