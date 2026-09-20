"""Testes unitários para app.ocr.image_processor (R6, Fase 3)."""

import base64
import io

import pytest

from app.ocr.image_processor import (
    ImageFormatError,
    OcrIndisponivelError,
    detect_image_format,
    extract_text_from_base64,
    extract_text_from_bytes,
)

# --- detect_image_format ---


def test_detect_jpeg():
    assert detect_image_format(b"\xff\xd8\xff\xe0" + b"\x00" * 10) == "JPEG"


def test_detect_png():
    assert detect_image_format(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10) == "PNG"


def test_detect_webp():
    assert detect_image_format(b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 10) == "WEBP"


def test_detect_unknown_returns_none():
    assert detect_image_format(b"\x00\x01\x02\x03") is None


# --- extract_text_from_bytes ---


def test_formato_invalido_levanta_image_format_error():
    with pytest.raises(ImageFormatError):
        extract_text_from_bytes(b"\x00\x01\x02\x03")


def test_ocr_extrai_texto_de_imagem_png(tmp_path):
    """Cria um PNG real com texto via Pillow e verifica que o OCR extrai algo."""
    pytest.importorskip("PIL", reason="Pillow não instalado")
    pytest.importorskip("pytesseract", reason="pytesseract não instalado")
    import subprocess

    if subprocess.run(["which", "tesseract"], capture_output=True).returncode != 0:
        pytest.skip("Tesseract não encontrado no PATH")

    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 50), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "TESTE", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = extract_text_from_bytes(buf.getvalue())
    assert "TESTE" in result.upper()


def test_ocr_indisponivel_levanta_erro_quando_tesseract_ausente(monkeypatch):
    """Simula Tesseract ausente e verifica que OcrIndisponivelError é levantado."""
    pytest.importorskip("PIL", reason="Pillow não instalado")
    import pytesseract
    from PIL import Image

    img = Image.new("RGB", (50, 50), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    monkeypatch.setattr(
        pytesseract,
        "image_to_string",
        lambda *a, **kw: (_ for _ in ()).throw(
            pytesseract.TesseractNotFoundError("tesseract not found")
        ),
    )
    with pytest.raises(OcrIndisponivelError):
        extract_text_from_bytes(buf.getvalue())


# --- extract_text_from_base64 ---


def test_base64_invalido_levanta_image_format_error():
    with pytest.raises(ImageFormatError):
        extract_text_from_base64("não-é-base64!!!")


def test_base64_valido_mas_formato_invalido():
    with pytest.raises(ImageFormatError):
        extract_text_from_base64(base64.b64encode(b"\x00\x01\x02\x03").decode())
