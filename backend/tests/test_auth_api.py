import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_auth_login_senha_incorreta(app_sqlite):
    async with AsyncClient(
        transport=ASGITransport(app=app_sqlite), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"email": "teste@example.com", "password": "senha_errada"},
        )
        assert resp.status_code == 401
        assert "Senha de demonstração incorreta" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_login_novo_cliente_criado_automaticamente(app_sqlite):
    async with AsyncClient(
        transport=ASGITransport(app=app_sqlite), base_url="http://test"
    ) as client:
        email = "marcos.silva@teste.com"
        resp = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "12345"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["token"].startswith("mock-token-")
        assert data["user"]["email"] == email
        assert data["user"]["nome"] == "Marcos Silva"
        assert data["user"]["perfil"] == "lead"

        # Confere GET /api/auth/me
        me_resp = await client.get(f"/api/auth/me?email={email}")
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == email


@pytest.mark.asyncio
async def test_auth_me_usuario_inexistente(app_sqlite):
    async with AsyncClient(
        transport=ASGITransport(app=app_sqlite), base_url="http://test"
    ) as client:
        resp = await client.get("/api/auth/me?email=naoexiste@teste.com")
        assert resp.status_code == 404
        assert "não encontrado" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_auth_register_usuario_simples_e_admin(app_sqlite):
    async with AsyncClient(
        transport=ASGITransport(app=app_sqlite), base_url="http://test"
    ) as client:
        # 1. Registro de usuário simples (Cliente)
        resp_cliente = await client.post(
            "/api/auth/register",
            json={
                "nome": "João Simples",
                "email": "joao.simples@example.com",
                "password": "12345",
                "perfil": "Cliente",
            },
        )
        assert resp_cliente.status_code == 201
        data_c = resp_cliente.json()
        assert data_c["user"]["nome"] == "João Simples"
        assert data_c["user"]["email"] == "joao.simples@example.com"
        assert data_c["user"]["perfil"] == "Cliente"

        # 2. Registro de usuário Admin
        resp_admin = await client.post(
            "/api/auth/register",
            json={
                "nome": "Carlos Admin",
                "email": "admin@example.com",
                "password": "12345",
                "perfil": "Admin",
            },
        )
        assert resp_admin.status_code == 201
        data_a = resp_admin.json()
        assert data_a["user"]["nome"] == "Carlos Admin"
        assert data_a["user"]["email"] == "admin@example.com"
        assert data_a["user"]["perfil"] == "Admin"

