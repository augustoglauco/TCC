import uuid
import pytest
from sqlalchemy import select
from app.db.models import AdminChart


@pytest.mark.asyncio
async def test_admin_chart_model_crud(db_session):
    chart = AdminChart(
        titulo="Vendas por Categoria",
        descricao="Gráfico de teste",
        tipo_grafico="bar",
        config_json={"x_key": "categoria", "y_keys": ["total_vendas_brl"]},
        dados_json=[{"categoria": "Elétrica", "total_vendas_brl": 1500.0}],
        sql_query="vendas_por_categoria",
        fixado=True,
        ordem=1,
        criado_por="admin@empresa.com",
    )
    db_session.add(chart)
    await db_session.commit()
    await db_session.refresh(chart)

    assert isinstance(chart.id, uuid.UUID)
    assert chart.titulo == "Vendas por Categoria"
    assert chart.fixado is True
    assert chart.dados_json[0]["categoria"] == "Elétrica"

    # Query back
    result = await db_session.scalar(select(AdminChart).where(AdminChart.id == chart.id))
    assert result is not None
    assert result.tipo_grafico == "bar"

    # Delete
    await db_session.delete(result)
    await db_session.commit()
    check = await db_session.scalar(select(AdminChart).where(AdminChart.id == chart.id))
    assert check is None
