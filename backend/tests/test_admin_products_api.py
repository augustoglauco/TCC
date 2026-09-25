import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app

@pytest.mark.asyncio
async def test_crud_admin_produtos():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cria produto manual
        resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Câmera Dome VIP 3200",
                "descricao": "Câmera Dome IP",
                "preco": "350.00",
                "categoria": "CFTV",
                "preco_base_fornecedor": "220.00",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        prod_id = data["id"]
        assert data["nome"] == "Câmera Dome VIP 3200"
        assert float(data["preco_base_fornecedor"]) == 220.0

        # 2. Lista produtos
        list_resp = await client.get("/api/admin/produtos?termo=Dome")
        assert list_resp.status_code == 200
        assert any(p["id"] == prod_id for p in list_resp.json()["items"])

        # 3. Atualiza produto
        put_resp = await client.put(f"/api/admin/produtos/{prod_id}", json={"preco": "399.00"})
        assert put_resp.status_code == 200
        assert float(put_resp.json()["preco"]) == 399.0

        # 4. Exclui produto
        del_resp = await client.delete(f"/api/admin/produtos/{prod_id}")
        assert del_resp.status_code == 204

        # 5. Confirma 404
        get_resp = await client.get(f"/api/admin/produtos/{prod_id}")
        assert get_resp.status_code == 404

@pytest.mark.asyncio
async def test_admin_produto_upload_e_delete_imagem(tmp_path, monkeypatch):
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "product_images_dir", str(tmp_path))

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Cria produto
        resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Switch 8 Portas",
                "descricao": "Switch Gigabit",
                "preco": "250.00",
                "categoria": "Redes",
            },
        )
        prod_id = resp.json()["id"]

        # Upload de foto avulsa
        files = {"file": ("switch.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")}
        upload_resp = await client.post(f"/api/admin/produtos/{prod_id}/imagens", files=files)
        assert upload_resp.status_code == 201
        img_data = upload_resp.json()
        assert img_data["imagem_url"].startswith("/api/uploads/produtos/")
        img_id = img_data["id"]

        # Consulta produto
        get_resp = await client.get(f"/api/admin/produtos/{prod_id}")
        assert get_resp.status_code == 200
        assert len(get_resp.json()["imagens"]) == 1

        # Deleta imagem
        del_img_resp = await client.delete(f"/api/admin/produtos/{prod_id}/imagens/{img_id}")
        assert del_img_resp.status_code == 204

        # Limpeza
        await client.delete(f"/api/admin/produtos/{prod_id}")
