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
