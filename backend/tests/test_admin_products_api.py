import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_crud_admin_produtos(app_sqlite, admin_headers):
    app = app_sqlite
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
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        prod_id = data["id"]
        assert data["nome"] == "Câmera Dome VIP 3200"
        assert float(data["preco_base_fornecedor"]) == 220.0

        # 2. Lista produtos
        list_resp = await client.get("/api/admin/produtos?termo=Dome", headers=admin_headers)
        assert list_resp.status_code == 200
        assert any(p["id"] == prod_id for p in list_resp.json()["items"])

        # 3. Atualiza produto
        put_resp = await client.put(
            f"/api/admin/produtos/{prod_id}", json={"preco": "399.00"}, headers=admin_headers
        )
        assert put_resp.status_code == 200
        assert float(put_resp.json()["preco"]) == 399.0

        # 4. Exclui produto
        del_resp = await client.delete(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
        assert del_resp.status_code == 204

        # 5. Confirma 404
        get_resp = await client.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_produto_upload_e_delete_imagem(app_sqlite, admin_headers):
    app = app_sqlite
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
            headers=admin_headers,
        )
        prod_id = resp.json()["id"]

        # Upload de foto avulsa
        files = {"file": ("switch.png", b"\x89PNG\r\n\x1a\nfakeimage", "image/png")}
        upload_resp = await client.post(
            f"/api/admin/produtos/{prod_id}/imagens", files=files, headers=admin_headers
        )
        assert upload_resp.status_code == 201
        img_data = upload_resp.json()
        assert img_data["imagem_url"].startswith("/api/uploads/produtos/")
        img_id = img_data["id"]

        # Consulta produto
        get_resp = await client.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
        assert get_resp.status_code == 200
        assert len(get_resp.json()["imagens"]) == 1

        # Deleta imagem
        del_img_resp = await client.delete(
            f"/api/admin/produtos/{prod_id}/imagens/{img_id}", headers=admin_headers
        )
        assert del_img_resp.status_code == 204

        # Limpeza
        await client.delete(f"/api/admin/produtos/{prod_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_admin_produto_estoque_desconto_compatibilidade(app_sqlite, admin_headers):
    app = app_sqlite
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cria 2 produtos
        p1 = (
            await client.post(
                "/api/admin/produtos",
                json={
                    "nome": "NVR 16 Canais",
                    "descricao": "Gravador IP",
                    "preco": "1200.00",
                    "categoria": "CFTV",
                },
                headers=admin_headers,
            )
        ).json()
        p2 = (
            await client.post(
                "/api/admin/produtos",
                json={
                    "nome": "HD 4TB Surveillance",
                    "descricao": "Disco Rígido",
                    "preco": "600.00",
                    "categoria": "CFTV",
                },
                headers=admin_headers,
            )
        ).json()

        try:
            # 2. Atualiza estoque de P1
            est_resp = await client.post(
                f"/api/admin/produtos/{p1['id']}/estoque",
                json={"centro_distribuicao": "CD-Matriz", "quantidade": 50},
                headers=admin_headers,
            )
            assert est_resp.status_code == 200
            assert any(e["quantidade"] == 50 for e in est_resp.json()["estoques"])

            # 3. Adiciona desconto por volume em P1
            desc_resp = await client.post(
                f"/api/admin/produtos/{p1['id']}/descontos-volume",
                json={"quantidade_minima": 5, "percentual_desconto": 10.0},
                headers=admin_headers,
            )
            assert desc_resp.status_code == 200
            desc_data = desc_resp.json()["descontos_volume"]
            assert len(desc_data) == 1
            desc_id = desc_data[0]["id"]

            # Remove desconto por volume
            del_desc_resp = await client.delete(
                f"/api/admin/produtos/{p1['id']}/descontos-volume/{desc_id}", headers=admin_headers
            )
            assert del_desc_resp.status_code == 200
            assert len(del_desc_resp.json()["descontos_volume"]) == 0

            # 4. Cadastra compatibilidade entre P1 e P2
            comp_resp = await client.post(
                f"/api/admin/produtos/{p1['id']}/compatibilidades",
                json={"compativel_com_id": p2["id"]},
                headers=admin_headers,
            )
            assert comp_resp.status_code == 200
            comp_list = comp_resp.json()
            assert len(comp_list) >= 1
            assert any(c["compativel_com_id"] == p2["id"] for c in comp_list)

            # Deleta compatibilidade
            del_comp = await client.delete(
                f"/api/admin/produtos/{p1['id']}/compatibilidades/{p2['id']}", headers=admin_headers
            )
            assert del_comp.status_code == 200

        finally:
            await client.delete(f"/api/admin/produtos/{p1['id']}", headers=admin_headers)
            await client.delete(f"/api/admin/produtos/{p2['id']}", headers=admin_headers)
