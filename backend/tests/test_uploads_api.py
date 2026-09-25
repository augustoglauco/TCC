import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app

@pytest.mark.asyncio
async def test_servimento_imagem_produto_inexistente_retorna_404():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/uploads/produtos/nao_existe.png")
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_servimento_imagem_produto_existente(tmp_path, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "product_images_dir", str(tmp_path))

    # Cria imagem fake
    img_file = tmp_path / "teste.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/uploads/produtos/teste.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == b"\x89PNG\r\n\x1a\nfakecontent"

@pytest.mark.asyncio
async def test_servimento_imagem_path_traversal_retorna_400(tmp_path, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "product_images_dir", str(tmp_path))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/uploads/produtos/../etc/passwd")
        assert resp.status_code in (400, 404)
