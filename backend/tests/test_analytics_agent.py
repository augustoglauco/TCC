import pytest
from decimal import Decimal
from app.db.models import AdminChart, Cliente, ClienteCompra, Produto
from app.services.analytics_agent import (
    extract_prompt_inline_data,
    process_dynamic_chart_request,
)


def test_extract_prompt_inline_data_key_value():
    prompt = "crie um gráfico de barras com os dados: São Paulo: 150, Rio de Janeiro: 90, Belo Horizonte: 60"
    res = extract_prompt_inline_data(prompt)
    assert res is not None
    assert res["tipo_grafico"] == "bar"
    assert len(res["dados"]) == 3
    assert res["dados"][0]["categoria"] == "São Paulo"
    assert res["dados"][0]["valor"] == 150.0
    assert res["config"]["format"] == "number"


def test_extract_prompt_inline_data_currency():
    prompt = "gráfico de pizza: Vendas SP: R$ 5000, Vendas RJ: R$ 3200, Vendas MG: R$ 1800"
    res = extract_prompt_inline_data(prompt)
    assert res is not None
    assert res["tipo_grafico"] == "pie"
    assert len(res["dados"]) == 3
    assert res["config"]["format"] == "currency"


def test_extract_prompt_inline_data_none_when_no_data():
    prompt = "qual é o horário de atendimento?"
    assert extract_prompt_inline_data(prompt) is None

    prompt_sem_valores = "mostre o estoque de geradores"
    assert extract_prompt_inline_data(prompt_sem_valores) is None


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_inline_data(db_session):
    prompt = "gere gráfico de barras: Projeto A: 40h, Projeto B: 65h, Projeto C: 20h"
    chart, explicacao = await process_dynamic_chart_request(
        session=db_session,
        prompt=prompt,
        user_email="admin@teste.com",
        llm_client=None,
    )
    assert chart is not None
    assert isinstance(chart, AdminChart)
    assert chart.tipo_grafico == "bar"
    assert chart.sql_query == "dynamic_user_data"
    assert len(chart.dados_json) == 3
    assert chart.dados_json[1]["categoria"] == "Projeto B"
    assert chart.dados_json[1]["valor"] == 65.0


@pytest.mark.asyncio
async def test_process_dynamic_chart_request_sql_data(db_session):
    p1 = Produto(nome="Gerador Turbo 1", descricao="Gerador potente", preco=Decimal("5000.00"), categoria="Geradores")
    p2 = Produto(nome="Gerador Turbo 2", descricao="Gerador potente", preco=Decimal("8000.00"), categoria="Geradores")
    db_session.add_all([p1, p2])
    await db_session.commit()

    prompt = "gere gráfico de produtos por faturamento"
    chart, explicacao = await process_dynamic_chart_request(
        session=db_session,
        prompt=prompt,
        user_email="admin@teste.com",
        llm_client=None,
    )
    assert chart is not None
    assert len(chart.dados_json) >= 2
    assert "produto" in chart.dados_json[0] or "nome" in chart.dados_json[0] or "categoria" in chart.dados_json[0]
