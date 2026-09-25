import io
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.catalog_extractor.extractor import (
    extract_page_products_local,
    extract_page_products_vision,
    extract_catalog_stream,
)
from app.models.catalog_extractor import (
    ExtractedProduct,
    CatalogConfirmRequest,
    CatalogConfirmItem,
)


@pytest.mark.asyncio
async def test_extract_page_products_local_retorna_produtos():
    local_client = AsyncMock()
    # Support both .response and .text
    mock_resp = MagicMock()
    mock_resp.response = '[{"nome": "Gravador NVD 1016", "descricao": "Gravador IP 16 canais", "categoria": "CFTV", "preco_base_fornecedor": 550.0, "preco": 799.0, "especificacoes_tecnicas": "16 canais PoE"}]'
    mock_resp.text = mock_resp.response
    local_client.generate = AsyncMock(return_value=mock_resp)

    texto_pagina = "Intelbras Gravador NVD 1016 16 canais PoE CFTV Preco R$ 550,00"
    produtos = await extract_page_products_local(texto_pagina, local_client)
    assert len(produtos) == 1
    assert produtos[0]["nome"] == "Gravador NVD 1016"
    assert produtos[0]["preco_base_fornecedor"] == 550.0


@pytest.mark.asyncio
async def test_extract_page_products_vision_retorna_produtos():
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='```json\n[{"nome": "Câmera Bullet VIP 1230", "descricao": "Câmera Bullet IP", "categoria": "CFTV", "preco_base_fornecedor": 210.0, "preco": 320.0, "especificacoes_tecnicas": "Full HD, IR 30m"}]\n```'
    )

    produtos = await extract_page_products_vision(b"fake-image-bytes", vision_client)
    assert len(produtos) == 1
    assert produtos[0]["nome"] == "Câmera Bullet VIP 1230"
    assert produtos[0]["preco"] == 320.0


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_imagem(tmp_path):
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Sensor IVP 3000", "descricao": "Sensor infravermelho", "categoria": "Alarmes", "preco_base_fornecedor": 45.0, "preco": 75.0, "especificacoes_tecnicas": "Sem fio"}]'
    )
    local_client = AsyncMock()

    files = [("foto_produto.jpg", b"fake-jpg-content")]
    events = []
    async for event in extract_catalog_stream(
        files=files,
        provider="external",
        fallback_external=True,
        temp_dir=tmp_path,
        local_client=local_client,
        vision_client=vision_client,
    ):
        events.append(event)

    assert any("event: progresso" in e for e in events)
    assert any("event: pagina_concluida" in e for e in events)
    assert any("event: done" in e for e in events)


@pytest.mark.asyncio
async def test_confirmar_catalogo_endpoint():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/admin/produtos/catalogo/confirmar",
            json={
                "produtos": [
                    {
                        "nome": "Produto Teste Lote",
                        "descricao": "Descricao do lote",
                        "categoria": "CFTV",
                        "preco_base_fornecedor": 100.0,
                        "preco": 150.0,
                        "especificacoes_tecnicas": "Especificacoes teste",
                    }
                ]
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["criados"] == 1
        assert len(data["produtos"]) == 1
        prod_id = data["produtos"][0]["id"]
        assert data["produtos"][0]["nome"] == "Produto Teste Lote"

        # Limpa o produto criado
        del_resp = await client.delete(f"/api/admin/produtos/{prod_id}")
        assert del_resp.status_code == 204

