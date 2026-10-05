import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.catalog_extractor.extractor import (
    _blocos_de_texto,
    extract_catalog_stream,
    extract_page_products_local,
    extract_page_products_vision,
)


@pytest.mark.asyncio
async def test_extract_page_products_local_retorna_produtos():
    local_client = AsyncMock()
    # Support both .response and .text
    mock_resp = MagicMock()
    mock_resp.response = '[{"nome": "Gravador NVD 1016", "descricao": "Gravador IP 16 canais", "categoria": "CFTV", "preco_base_fornecedor": 550.0, "preco": 799.0, "especificacoes_tecnicas": "16 canais PoE"}]'  # noqa: E501
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
        return_value='```json\n[{"nome": "Câmera Bullet VIP 1230", "descricao": "Câmera Bullet IP", "categoria": "CFTV", "preco_base_fornecedor": 210.0, "preco": 320.0, "especificacoes_tecnicas": "Full HD, IR 30m"}]\n```'  # noqa: E501
    )

    produtos = await extract_page_products_vision(b"fake-image-bytes", vision_client)
    assert len(produtos) == 1
    assert produtos[0]["nome"] == "Câmera Bullet VIP 1230"
    assert produtos[0]["preco"] == 320.0


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_imagem(tmp_path):
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Sensor IVP 3000", "descricao": "Sensor infravermelho", "categoria": "Alarmes", "preco_base_fornecedor": 45.0, "preco": 75.0, "especificacoes_tecnicas": "Sem fio"}]'  # noqa: E501
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


async def test_extract_catalog_stream_imagem_com_falha_de_visao_reporta_erro(tmp_path):
    """Falha na visão externa (ex.: 429 esgotado) vira `erro` no resultado da
    página — distinto de "nenhum produto encontrado" para o frontend não
    confundir um erro de extração com uma página genuinamente vazia."""
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(side_effect=RuntimeError("429 Too Many Requests"))

    files = [("foto_produto.jpg", b"fake-jpg-content")]
    events = []
    async for event in extract_catalog_stream(
        files=files,
        provider="external",
        fallback_external=True,
        temp_dir=tmp_path,
        local_client=None,
        vision_client=vision_client,
    ):
        events.append(event)

    pagina_evento = next(e for e in events if "event: pagina_concluida" in e)
    payload = json.loads(pagina_evento.split("data: ", 1)[1])
    assert payload["produtos"] == []
    assert payload["erro"] is not None
    assert "429" in payload["erro"]


async def test_extract_catalog_stream_imagem_sem_vision_client_reporta_erro(tmp_path):
    files = [("foto_produto.jpg", b"fake-jpg-content")]
    events = []
    async for event in extract_catalog_stream(
        files=files,
        provider="external",
        fallback_external=True,
        temp_dir=tmp_path,
        local_client=None,
        vision_client=None,
    ):
        events.append(event)

    pagina_evento = next(e for e in events if "event: pagina_concluida" in e)
    payload = json.loads(pagina_evento.split("data: ", 1)[1])
    assert payload["produtos"] == []
    assert payload["erro"] == "Modelo de visão externo não configurado."


@pytest.mark.asyncio
async def test_confirmar_catalogo_endpoint(app_sqlite, admin_headers):
    from httpx import ASGITransport, AsyncClient

    app = app_sqlite
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
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["criados"] == 1
        assert len(data["produtos"]) == 1
        prod_id = data["produtos"][0]["id"]
        assert data["produtos"][0]["nome"] == "Produto Teste Lote"

        # Limpa o produto criado
        del_resp = await client.delete(f"/api/admin/produtos/{prod_id}", headers=admin_headers)
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
async def test_upload_temp_endpoint(app_sqlite, admin_headers):
    from httpx import ASGITransport, AsyncClient

    app = app_sqlite
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"  # noqa: E501
        files = {"file": ("manual_upload.png", fake_png, "image/png")}
        resp = await client.post(
            "/api/admin/produtos/upload-temp", files=files, headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "imagem_temp_url" in data
        assert data["imagem_temp_url"].startswith("/api/uploads/produtos/temp/")


@pytest.mark.asyncio
async def test_confirmar_catalogo_com_imagem_temp(app_sqlite, tmp_path, admin_headers):
    from httpx import ASGITransport, AsyncClient

    # Cria arquivo temporário real no diretório de temp
    temp_dir = tmp_path / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_img_file = temp_dir / "crop_teste123.jpg"
    temp_img_file.write_bytes(
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"  # noqa: E501
    )

    with patch("app.api.admin_products.get_settings") as mock_settings:
        mock_s = MagicMock()
        mock_s.product_images_dir = str(tmp_path)
        mock_settings.return_value = mock_s

        app = app_sqlite
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
                headers=admin_headers,
            )
            assert resp.status_code == 201
            data = resp.json()
            assert data["criados"] == 1
            prod = data["produtos"][0]
            assert prod["imagem_url"] is not None
            assert isinstance(prod["imagem_url"], str)
            assert prod["imagem_url"].startswith("/api/uploads/produtos/")

            # Limpa
            await client.delete(f"/api/admin/produtos/{prod['id']}", headers=admin_headers)


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_pdf_figuras(tmp_path):
    from pathlib import Path

    pdf_path = (
        Path(__file__).resolve().parent.parent.parent
        / "docs"
        / "Manuais_fornecedor"
        / "Datasheet - iNVU 9164 M2 IAX FT.pdf"
    )
    if not pdf_path.exists():
        pytest.skip("PDF de teste não encontrado")

    pdf_bytes = pdf_path.read_bytes()
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Gravador iNVU 9164", "descricao": "Gravador de alta capacidade", "categoria": "CFTV", "preco_base_fornecedor": 1500.0, "preco": 2200.0, "especificacoes_tecnicas": "64 canais"}]'  # noqa: E501
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


def test_parse_page_range():
    from app.catalog_extractor.extractor import _parse_page_range

    # Casos vazios -> None (todas as páginas)
    assert _parse_page_range(None, 10) is None
    assert _parse_page_range("", 10) is None
    assert _parse_page_range("   ", 10) is None

    # Intervalo simples
    assert _parse_page_range("1-3", 10) == {1, 2, 3}

    # Páginas avulsas
    assert _parse_page_range("2, 5, 8", 10) == {2, 5, 8}

    # Intervalo aberto no fim ("3-")
    assert _parse_page_range("3-", 5) == {3, 4, 5}

    # Intervalo aberto no início ("-3")
    assert _parse_page_range("-3", 5) == {1, 2, 3}

    # Combinação de intervalos e páginas avulsas
    assert _parse_page_range("1-2, 5, 7-8", 10) == {1, 2, 5, 7, 8}

    # Invertido ("5-3")
    assert _parse_page_range("5-3", 10) == {3, 4, 5}

    # Fora dos limites (descarta páginas <= 0 ou > max_pages)
    assert _parse_page_range("0, 3, 25", 10) == {3}


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_filtro_page_range(tmp_path):
    from pathlib import Path

    pdf_path = (
        Path(__file__).resolve().parent.parent.parent
        / "docs"
        / "Manuais_fornecedor"
        / "Datasheet - iNVU 9164 M2 IAX FT.pdf"
    )
    if not pdf_path.exists():
        pytest.skip("PDF de teste não encontrado")

    pdf_bytes = pdf_path.read_bytes()
    vision_client = AsyncMock()
    vision_client.describe_image = AsyncMock(
        return_value='[{"nome": "Produto Pagina 2", "descricao": "Desc", "categoria": "CFTV", "preco_base_fornecedor": 100.0, "preco": 150.0}]'  # noqa: E501
    )
    local_client = AsyncMock()

    events = []
    # Solicita especificamente apenas a página 2 do PDF
    async for event in extract_catalog_stream(
        files=[("datasheet.pdf", pdf_bytes)],
        provider="external",
        fallback_external=False,
        temp_dir=tmp_path,
        local_client=local_client,
        vision_client=vision_client,
        page_range="2",
    ):
        events.append(event)

    pagina_events = [e for e in events if "event: pagina_concluida" in e]
    # Deve processar exatamente 1 página
    assert len(pagina_events) == 1
    p_data = json.loads(pagina_events[0].split("data: ")[1].strip())
    # A página de origem deve ser 2
    assert p_data["pagina"] == 2
    assert p_data["total_paginas"] == 1
    assert p_data["produtos"][0]["pagina_origem"] == 2


def test_blocos_de_texto_divide_por_linhas_e_aceita_latin1():
    linhas = [f"Produto {i} - R$ {i},00" for i in range(200)]
    blocos = _blocos_de_texto("\n".join(linhas).encode("utf-8"), max_chars=500)
    assert len(blocos) > 1
    assert all(len(b) <= 500 for b in blocos)
    assert "\n".join(blocos).split("\n") == linhas

    assert _blocos_de_texto("Câmera Ação".encode("latin-1")) == ["Câmera Ação"]
    assert _blocos_de_texto(b"   \n  ") == []
    assert _blocos_de_texto(b"x" * 25, max_chars=10) == ["x" * 10, "x" * 10, "x" * 5]


@pytest.mark.asyncio
async def test_extract_catalog_stream_com_arquivo_de_texto(tmp_path):
    local_client = AsyncMock()
    resp = MagicMock()
    resp.response = resp.text = (
        '[{"nome": "Central de Alarme AMT 4010", "categoria": "Alarmes", "preco_base_fornecedor": 480.0}]'  # noqa: E501
    )
    local_client.generate = AsyncMock(return_value=resp)
    vision_client = AsyncMock()

    events = [
        e
        async for e in extract_catalog_stream(
            files=[("lista.txt", b"Central de Alarme AMT 4010 - R$ 480,00")],
            provider="local",
            fallback_external=True,
            temp_dir=tmp_path,
            local_client=local_client,
            vision_client=vision_client,
        )
    ]

    pagina = next(e for e in events if "event: pagina_concluida" in e)
    dados = json.loads(pagina.split("data: ", 1)[1])
    assert dados["produtos"][0]["nome"] == "Central de Alarme AMT 4010"
    assert dados["produtos"][0]["preco_base_fornecedor"] == 480.0
    assert dados["produtos"][0]["imagem_temp_url"] is None
    assert any("event: done" in e for e in events)
    vision_client.describe_image.assert_not_called()
