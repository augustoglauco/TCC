from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from app.db.models import AdminChart, Cliente, Produto
from app.main import create_app
from app.api.rag_dependencies import get_db_session


@pytest.fixture
def test_app(db_session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


@pytest.mark.asyncio
async def test_admin_charts_api_unauthorized(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/charts")
        assert res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_admin_charts_crud_flow(test_app, db_session):
    admin = Cliente(nome="Admin Master", email="admin@empresa.com")
    db_session.add(admin)
    p = Produto(nome="Produto 1", descricao="Desc", preco=Decimal("100.00"), categoria="Ferramentas")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(admin)

    admin_token = f"mock-token-{admin.id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create chart
        payload = {
            "titulo": "Gráfico de Teste",
            "descricao": "Descrição do teste",
            "tipo_grafico": "bar",
            "config_json": {"x_key": "categoria", "y_keys": ["total"]},
            "dados_json": [{"categoria": "Ferramentas", "total": 100.0}],
            "sql_query": "vendas_por_categoria",
            "fixado": True,
            "ordem": 0,
        }
        res_create = await client.post("/api/admin/charts", json=payload, headers=headers)
        assert res_create.status_code == 201
        created = res_create.json()
        chart_id = created["id"]
        assert created["titulo"] == "Gráfico de Teste"

        # 2. List charts
        res_list = await client.get("/api/admin/charts", headers=headers)
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1
        assert any(c["id"] == chart_id for c in items)

        # 3. Refresh chart
        res_refresh = await client.post(f"/api/admin/charts/{chart_id}/refresh", headers=headers)
        assert res_refresh.status_code == 200
        refreshed = res_refresh.json()
        assert len(refreshed["dados_json"]) >= 1

        # 4. Update chart
        res_update = await client.put(
            f"/api/admin/charts/{chart_id}",
            json={"titulo": "Novo Título", "fixado": False},
            headers=headers,
        )
        assert res_update.status_code == 200
        assert res_update.json()["titulo"] == "Novo Título"
        assert res_update.json()["fixado"] is False

        # 5. Delete chart
        res_del = await client.delete(f"/api/admin/charts/{chart_id}", headers=headers)
        assert res_del.status_code == 200

        # Verify deletion
        res_list_after = await client.get("/api/admin/charts", headers=headers)
        assert not any(c["id"] == chart_id for c in res_list_after.json())


@pytest.mark.asyncio
async def test_admin_charts_refresh_dynamic_sql_and_user_data(test_app, db_session):
    admin = Cliente(nome="Admin Dynamic", email="admin@empresa.com")
    db_session.add(admin)
    p = Produto(nome="Item Dynamic", descricao="Desc", preco=Decimal("250.00"), categoria="Ferramentas")
    db_session.add(p)
    await db_session.commit()
    await db_session.refresh(admin)

    admin_token = f"mock-token-{admin.id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dynamic SQL chart
        payload_sql = {
            "titulo": "Gráfico SQL Dinâmico",
            "tipo_grafico": "bar",
            "config_json": {"x_key": "nome", "y_keys": ["preco"]},
            "dados_json": [],
            "sql_query": "dynamic_sql: SELECT nome, preco FROM produtos WHERE nome = 'Item Dynamic'",
        }
        res1 = await client.post("/api/admin/charts", json=payload_sql, headers=headers)
        assert res1.status_code == 201
        chart_id1 = res1.json()["id"]

        res_ref1 = await client.post(f"/api/admin/charts/{chart_id1}/refresh", headers=headers)
        assert res_ref1.status_code == 200
        dados1 = res_ref1.json()["dados_json"]
        assert len(dados1) == 1
        assert dados1[0]["nome"] == "Item Dynamic"
        assert dados1[0]["preco"] == 250.0

        # Dynamic user data chart
        payload_user = {
            "titulo": "Gráfico Usuário",
            "tipo_grafico": "pie",
            "config_json": {"x_key": "cat", "y_keys": ["val"]},
            "dados_json": [{"cat": "A", "val": 10}, {"cat": "B", "val": 20}],
            "sql_query": "dynamic_user_data",
        }
        res2 = await client.post("/api/admin/charts", json=payload_user, headers=headers)
        assert res2.status_code == 201
        chart_id2 = res2.json()["id"]

        res_ref2 = await client.post(f"/api/admin/charts/{chart_id2}/refresh", headers=headers)
        assert res_ref2.status_code == 200
        dados2 = res_ref2.json()["dados_json"]
        assert len(dados2) == 2
        assert dados2[0]["cat"] == "A"


@pytest.mark.asyncio
async def test_admin_charts_refresh_dynamic_sql_rejeita_tabela_fora_do_allowlist(
    test_app, db_session
):
    # Achado da revisão de 2026-10-04: sem rollback, uma falha aqui deixava
    # a sessão presa e o erro era engolido com 200 devolvendo dados obsoletos.
    admin = Cliente(nome="Admin Dynamic", email="admin@empresa.com")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    headers = {"Authorization": f"Bearer mock-token-{admin.id}"}
    transport = ASGITransport(app=test_app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload_sql = {
            "titulo": "Gráfico SQL Inseguro",
            "tipo_grafico": "bar",
            "config_json": {"x_key": "key", "y_keys": ["val"]},
            "dados_json": [{"key": "antigo", "val": 1}],
            "sql_query": "dynamic_sql: SELECT * FROM app_settings",
        }
        res_create = await client.post("/api/admin/charts", json=payload_sql, headers=headers)
        assert res_create.status_code == 201
        chart_id = res_create.json()["id"]

        res_refresh = await client.post(f"/api/admin/charts/{chart_id}/refresh", headers=headers)
        assert res_refresh.status_code == 400

        # A sessão não ficou presa em estado de rollback pendente — uma
        # requisição seguinte continua funcionando normalmente.
        res_list = await client.get("/api/admin/charts", headers=headers)
        assert res_list.status_code == 200

