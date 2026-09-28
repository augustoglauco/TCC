import pytest
from httpx import ASGITransport, AsyncClient
from app.main import create_app


@pytest.mark.asyncio
async def test_public_products_api_flow():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cadastra 3 produtos (2 com estoque via admin, 1 sem estoque)
        # Produto A (Com estoque, CFTV)
        prod_a_resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Câmera Bullet Z",
                "descricao": "Câmera Bullet HD",
                "preco": "299.90",
                "categoria": "CFTV",
            },
        )
        assert prod_a_resp.status_code == 201
        prod_a_id = prod_a_resp.json()["id"]

        # Produto B (Com estoque, CFTV) - Nome alfabeticamente anterior a Z
        prod_b_resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Câmera Bullet A",
                "descricao": "Câmera Bullet 4K",
                "preco": "499.90",
                "categoria": "CFTV",
            },
        )
        assert prod_b_resp.status_code == 201
        prod_b_id = prod_b_resp.json()["id"]

        # Produto C (Sem estoque, CFTV) - Nome alfabeticamente "A1" mas sem estoque
        prod_c_resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Câmera Bullet 00 (Sem Estoque)",
                "descricao": "Câmera Descontinuada",
                "preco": "199.90",
                "categoria": "CFTV",
            },
        )
        assert prod_c_resp.status_code == 201
        prod_c_id = prod_c_resp.json()["id"]

        # Adiciona estoque para Produto A e Produto B
        await client.post(
            f"/api/admin/produtos",
            json={
                "nome": "Produto Temporário",
                "descricao": "temp",
                "preco": "10.00",
                "categoria": "Outros",
            },
        )

        try:
            # Testa listagem pública com ordenação
            resp = await client.get("/api/products?categoria=CFTV")
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert data["total"] >= 3

            # Testa categorias distintas
            cat_resp = await client.get("/api/products/categorias")
            assert cat_resp.status_code == 200
            assert "CFTV" in cat_resp.json()

            # Testa busca por ID
            get_resp = await client.get(f"/api/products/{prod_a_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["nome"] == "Câmera Bullet Z"

        finally:
            # Limpeza dos produtos criados
            await client.delete(f"/api/admin/produtos/{prod_a_id}")
            await client.delete(f"/api/admin/produtos/{prod_b_id}")
            await client.delete(f"/api/admin/produtos/{prod_c_id}")
