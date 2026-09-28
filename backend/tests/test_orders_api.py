import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_orders_api_full_flow(app_sqlite):
    app = app_sqlite
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Cadastra um produto com estoque e faixas de desconto
        prod_resp = await client.post(
            "/api/admin/produtos",
            json={
                "nome": "Inversor Solar 5KW",
                "descricao": "Inversor de alta eficiência",
                "preco": "2500.00",
                "categoria": "Energia Solar",
                "peso_kg": "12.50",
            },
        )
        assert prod_resp.status_code == 201
        prod_id = prod_resp.json()["id"]

        # Adiciona 50 unidades de estoque no CD-SP
        est_resp = await client.post(
            f"/api/admin/produtos/{prod_id}/estoque",
            json={"centro_distribuicao": "CD-SP", "quantidade": 50},
        )
        assert est_resp.status_code == 200

        # Adiciona desconto por volume (10+ un -> 10% desc)
        desc_resp = await client.post(
            f"/api/admin/produtos/{prod_id}/descontos-volume",
            json={"quantidade_minima": 10, "percentual_desconto": "10.00"},
        )
        assert desc_resp.status_code == 200

        try:
            # 2. Testar Simulação de Cotação (/api/orders/quote)
            quote_resp = await client.post(
                "/api/orders/quote",
                json={
                    "itens": [
                        {"produto_id": prod_id, "quantidade": 10, "centro_distribuicao": "CD-SP"}
                    ]
                },
            )
            assert quote_resp.status_code == 200
            quote_data = quote_resp.json()
            # 2500 * 10 * 0.90 = 22500.00
            assert float(quote_data["valor_total"]) == 22500.0
            assert quote_data["itens"][0]["percentual_desconto_aplicado"] == "10.00"

            # 3. Testar Cálculo de Frete (/api/orders/freight)
            freight_resp = await client.post(
                "/api/orders/freight",
                json={
                    "cep": "01000-000",  # SP Capital -> Custo base R$ 35.00
                    "itens": [
                        {"produto_id": prod_id, "quantidade": 2, "centro_distribuicao": "CD-SP"}
                    ],
                },
            )
            assert freight_resp.status_code == 200
            freight_data = freight_resp.json()
            assert freight_data["prazo_dias"] == 2
            # Peso = 12.5 * 2 = 25kg. Custo = 35 + (25 * 2.5) = 35 + 62.5 = 97.50
            assert float(freight_data["custo_estimado"]) == 97.50

            # 4. Criar Pedido (/api/orders)
            order_resp = await client.post(
                "/api/orders",
                json={
                    "user_email": "cliente@empresa.com",
                    "itens": [
                        {"produto_id": prod_id, "quantidade": 5, "centro_distribuicao": "CD-SP"}
                    ],
                },
            )
            assert order_resp.status_code == 201
            order_data = order_resp.json()
            assert order_data["status"] == "reservado"
            assert order_data["user_email"] == "cliente@empresa.com"
            order_id = order_data["id"]

            # 5. Listar Pedidos (/api/orders)
            list_resp = await client.get("/api/orders?user_email=cliente@empresa.com")
            assert list_resp.status_code == 200
            list_data = list_resp.json()
            assert list_data["total"] >= 1
            assert any(item["id"] == order_id for item in list_data["items"])

            # 6. Obter Pedido por ID (/api/orders/{id})
            get_resp = await client.get(f"/api/orders/{order_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["id"] == order_id

            # 7. Tentar pedir mais do que o estoque restante (restavam 45; pede 50)
            fail_resp = await client.post(
                "/api/orders",
                json={
                    "user_email": "cliente@empresa.com",
                    "itens": [
                        {"produto_id": prod_id, "quantidade": 50, "centro_distribuicao": "CD-SP"}
                    ],
                },
            )
            assert fail_resp.status_code == 400
            assert "insuficiente" in fail_resp.json()["detail"].lower()

        finally:
            await client.delete(f"/api/admin/produtos/{prod_id}")
