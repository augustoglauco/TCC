"""OCR para imagens dirigidas (R6) — extrai texto de PNG/JPG via pytesseract.

# MVP: uso dirigido (comprovantes, documentos solicitados pelo sistema) —
# sem classificação automática de tipo de imagem nem pré-processamento
# avançado (binarização, deskew). Só extrai texto; busca por similaridade
# visual via CLIP fica para o próximo item da Fase 3.
"""

import base64
import binascii
import io
import logging

logger = logging.getLogger(__name__)

# Formatos aceitos (detectados pelo magic bytes, não pela extensão).
_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG": "PNG",
    b"RIFF": "WEBP",  # RIFF????WEBP
}


def detect_image_format(data: bytes) -> str | None:
    """Detecta o formato da imagem pelos magic bytes. Retorna 'JPEG', 'PNG',
    'WEBP' ou None se não reconhecido."""
    for magic, fmt in _MAGIC.items():
        if data[: len(magic)] == magic:
            return fmt
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None


# Alias privado mantido para compatibilidade interna do módulo.
_detect_format = detect_image_format


class ImageFormatError(ValueError):
    """Formato de imagem não suportado ou dados corrompidos."""


class OcrIndisponivelError(RuntimeError):
    """pytesseract/Tesseract não está instalado ou não pode ser executado."""


def extract_text_from_bytes(image_bytes: bytes) -> str:
    """Extrai texto de `image_bytes` (PNG/JPG/WEBP) via Tesseract OCR.

    Retorna string vazia se não houver texto reconhecível.
    Levanta `ImageFormatError` para formato inválido/corrompido e
    `OcrIndisponivelError` se o Tesseract não estiver disponível.
    """
    fmt = _detect_format(image_bytes)
    if fmt is None:
        raise ImageFormatError("Formato de imagem não suportado. Use PNG, JPG ou WEBP.")

    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OcrIndisponivelError(
            "pytesseract/Pillow não instalado — adicione ao pyproject.toml."
        ) from exc

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:
        raise ImageFormatError(f"Não foi possível abrir a imagem: {exc}") from exc

    try:
        # lang="por+eng": tenta português primeiro, inglês como fallback —
        # adequado para documentos/comprovantes brasileiros com termos em inglês.
        text: str = pytesseract.image_to_string(image, lang="por+eng")
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrIndisponivelError("Tesseract não encontrado no PATH do sistema.") from exc
    except Exception as exc:
        raise OcrIndisponivelError(f"Erro ao executar OCR: {exc}") from exc

    return text.strip()


def extract_text_from_base64(image_b64: str) -> str:
    """Decodifica base64 e extrai texto via OCR.

    Levanta `ImageFormatError` para base64 inválido ou formato não suportado.
    """
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageFormatError("Campo 'image' não é base64 válido.") from exc
    return extract_text_from_bytes(image_bytes)
