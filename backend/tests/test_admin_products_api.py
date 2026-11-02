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
async def test_admin_produto_familia_opcional_grava_e_atualiza(app_sqlite, admin_headers):
    """`familia` agrupa modelos do mesmo produto (cada modelo é uma linha): é
    opcional, volta na API e pode ser trocada ou limpa pelo PUT."""
    base = {
        "descricao": "Controlador de acesso",
        "preco": "900.00",
        "categoria": "Controle de Acesso",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app_sqlite), base_url="http://test"
    ) as client:
        sem_familia = await client.post(
            "/api/admin/produtos", json={**base, "nome": "Avulso"}, headers=admin_headers
        )
        assert sem_familia.status_code == 201
        assert sem_familia.json()["familia"] is None

        criado = await client.post(
            "/api/admin/produtos",
            json={**base, "nome": "iDAccess — Pro", "familia": "iDAccess"},
            headers=admin_headers,
        )
        assert criado.status_code == 201
        assert criado.json()["familia"] == "iDAccess"
        prod_id = criado.json()["id"]

        trocado = await client.put(
            f"/api/admin/produtos/{prod_id}",
            json={"familia": "iDAccess Linha 2"},
            headers=admin_headers,
        )
        assert trocado.json()["familia"] == "iDAccess Linha 2"

        limpo = await client.put(
            f"/api/admin/produtos/{prod_id}", json={"familia": None}, headers=admin_headers
        )
        assert limpo.json()["familia"] is None

        longa = await client.post(
            "/api/admin/produtos",
            json={**base, "nome": "X", "familia": "a" * 121},
            headers=admin_headers,
        )
        assert longa.status_code == 422


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


@pytest.mark.asyncio
async def test_delete_imagem_principal_reatribui_outra(app_sqlite, admin_headers):
    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as c:
        resp = await c.post(
            "/api/admin/produtos",
            json={
                "nome": "Roteador AX",
                "descricao": "Wi-Fi 6",
                "preco": "300.00",
                "categoria": "Redes",
            },
            headers=admin_headers,
        )
        prod_id = resp.json()["id"]
        urls = []
        ids = []
        for nome in ("a.png", "b.png"):
            files = {"file": (nome, b"\x89PNG\r\n\x1a\n" + nome.encode(), "image/png")}
            r = await c.post(
                f"/api/admin/produtos/{prod_id}/imagens", files=files, headers=admin_headers
            )
            urls.append(r.json()["imagem_url"])
            ids.append(r.json()["id"])

        assert (await c.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)).json()[
            "imagem_url"
        ] == urls[1]

        # Remove a principal (b): produto passa a apontar para a outra (a)
        r = await c.delete(f"/api/admin/produtos/{prod_id}/imagens/{ids[1]}", headers=admin_headers)
        assert r.status_code == 204
        prod = (await c.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)).json()
        assert prod["imagem_url"] == urls[0]

        # Remove a última: imagem_url fica None
        await c.delete(f"/api/admin/produtos/{prod_id}/imagens/{ids[0]}", headers=admin_headers)
        prod = (await c.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)).json()
        assert prod["imagem_url"] is None

        # Imagem inexistente: 404
        r = await c.delete(f"/api/admin/produtos/{prod_id}/imagens/999999", headers=admin_headers)
        assert r.status_code == 404

        await c.delete(f"/api/admin/produtos/{prod_id}", headers=admin_headers)


@pytest.mark.asyncio
async def test_escolher_imagem_principal(app_sqlite, admin_headers):
    async with AsyncClient(transport=ASGITransport(app=app_sqlite), base_url="http://test") as c:
        resp = await c.post(
            "/api/admin/produtos",
            json={"nome": "Câmera X", "descricao": "d", "preco": "10.00", "categoria": "CFTV"},
            headers=admin_headers,
        )
        prod_id = resp.json()["id"]
        imgs = []
        for nome in ("a.png", "b.png", "c.png"):
            files = {"file": (nome, b"\x89PNG\r\n\x1a\n" + nome.encode(), "image/png")}
            r = await c.post(
                f"/api/admin/produtos/{prod_id}/imagens",
                files=files,
                data={"is_principal": "false"},
                headers=admin_headers,
            )
            imgs.append(r.json())

        async def produto():
            r = await c.get(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
            return r.json()

        # Sem escolha explícita, a primeira foto vira a padrão; as seguintes não a trocam.
        assert [i["is_principal"] for i in imgs] == [True, False, False]
        assert (await produto())["imagem_url"] == imgs[0]["imagem_url"]

        r = await c.put(
            f"/api/admin/produtos/{prod_id}/imagens/{imgs[2]['id']}/principal",
            headers=admin_headers,
        )
        assert r.status_code == 200
        p = await produto()
        assert p["imagem_url"] == imgs[2]["imagem_url"]
        assert [i["is_principal"] for i in p["imagens"]] == [False, False, True]

        # Upload marcado como padrão rebaixa a anterior.
        files = {"file": ("d.png", b"\x89PNG\r\n\x1a\nd", "image/png")}
        r = await c.post(
            f"/api/admin/produtos/{prod_id}/imagens",
            files=files,
            data={"is_principal": "true"},
            headers=admin_headers,
        )
        p = await produto()
        assert p["imagem_url"] == r.json()["imagem_url"]
        assert sum(i["is_principal"] for i in p["imagens"]) == 1

        r = await c.put(
            f"/api/admin/produtos/{prod_id}/imagens/999999/principal", headers=admin_headers
        )
        assert r.status_code == 404
        await c.delete(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
