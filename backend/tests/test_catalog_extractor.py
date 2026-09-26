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


def test_extrair_figuras_pagina_filtra_ruido_e_recorta(tmp_path):
    from PIL import Image
    from app.catalog_extractor.extractor import _extrair_figuras_pagina

    # Cria imagem de página simulada 600x800
    pil_page = Image.new("RGB", (600, 800), color=(255, 255, 255))

    # Mock do objeto Page do pdfplumber
    mock_page = MagicMock()
    mock_page.width = 600.0
    mock_page.height = 800.0
    mock_page.images = [
        # 1. Ícone minúsculo / bullet (deve ser ignorado)
        {"x0": 10.0, "top": 10.0, "width": 15.0, "height": 15.0},
        # 2. Divisor estreito horizontal (deve ser ignorado)
        {"x0": 50.0, "top": 100.0, "width": 500.0, "height": 2.0},
        # 3. Logo no cabeçalho superior (deve ser ignorado)
        {"x0": 20.0, "top": 10.0, "width": 120.0, "height": 30.0},
        # 4. Imagem válida do produto 1 (centro-esquerda)
        {"x0": 50.0, "top": 150.0, "width": 120.0, "height": 100.0},
        # 5. Duplicata quase idêntica do produto 1 (deve ser ignorada)
        {"x0": 51.0, "top": 151.0, "width": 120.0, "height": 100.0},
        # 6. Imagem válida do produto 2 (centro-direita)
        {"x0": 250.0, "top": 150.0, "width": 120.0, "height": 100.0},
    ]

    urls = _extrair_figuras_pagina(mock_page, pil_page, tmp_path)
    assert len(urls) == 2
    assert all("crop_" in u for u in urls)


@pytest.mark.asyncio
async def test_upload_temp_endpoint():
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app

    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"file": ("manual_upload.png", fake_png, "image/png")}
        resp = await client.post("/api/admin/produtos/upload-temp", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert "imagem_temp_url" in data
        assert data["imagem_temp_url"].startswith("/api/uploads/produtos/temp/")


@pytest.mark.asyncio
async def test_confirmar_catalogo_com_imagem_temp(tmp_path):
    from httpx import ASGITransport, AsyncClient
    from app.main import create_app
    from app.config import get_settings

    # Cria arquivo temporário real no diretório de temp
    settings = get_settings()
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_img_file = temp_dir / "crop_teste123.jpg"
    temp_img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9")

    with patch("app.api.admin_products.get_settings") as mock_settings:
        mock_s = MagicMock()
        mock_s.product_images_dir = str(tmp_path)
        mock_settings.return_value = mock_s

        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/admin/produtos/catalogo/confirmar",
                json={
                    "produtos": [
                        {
                            "nome": "Produto Com Foto Recortada",
                            "descricao": "Descricao",
                            "categoria": "CFTV",
                            "preco_base_fornecedor": 120.0,
                            "preco": 180.0,
                            "imagem_temp_url": "/api/uploads/produtos/temp/crop_teste123.jpg",
                        }
                    ]
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["criados"] == 1
            prod = data["produtos"][0]
            assert prod["imagem_url"] is not None
            assert isinstance(prod["imagem_url"], str)
            assert prod["imagem_url"].startswith("/api/uploads/produtos/")

            # Limpa
            await client.delete(f"/api/admin/produtos/{prod['id']}")


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_pdf_figuras(tmp_path):
    from pathlib import Path
    pdf_path = Path(__file__).resolve().parent.parent.parent / "docs" / "Manuais_fornecedor" / "Datasheet - iNVU 9164 M2 IAX FT.pdf"
    if not pdf_path.exists():
        pytest.skip("PDF de teste não encontrado")

    pdf_bytes = pdf_path.read_bytes()
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Gravador iNVU 9164", "descricao": "Gravador de alta capacidade", "categoria": "CFTV", "preco_base_fornecedor": 1500.0, "preco": 2200.0, "especificacoes_tecnicas": "64 canais"}]'
    )
    local_client = AsyncMock()

    events = []
    async for event in extract_catalog_stream(
        files=[("datasheet.pdf", pdf_bytes)],
        provider="external",
        fallback_external=False,
        temp_dir=tmp_path,
        local_client=local_client,
        vision_client=vision_client,
    ):
        events.append(event)

    pagina_events = [e for e in events if "event: pagina_concluida" in e]
    assert len(pagina_events) >= 1
    # Verifica a primeira página que contém figuras
    p1_data = json.loads(pagina_events[0].split("data: ")[1].strip())

    assert "fotos_pagina" in p1_data
    assert len(p1_data["fotos_pagina"]) > 0
    # O preview da página é cat_
    assert p1_data["imagem_preview_url"].startswith("/api/uploads/produtos/temp/cat_")
    # A foto do produto individual é a figura recortada crop_, NÃO a página inteira cat_!
    prod = p1_data["produtos"][0]
    assert prod["imagem_temp_url"].startswith("/api/uploads/produtos/temp/crop_")
    assert prod["imagem_temp_url"] != p1_data["imagem_preview_url"]
    assert len(prod["fotos_pagina"]) == len(p1_data["fotos_pagina"])


