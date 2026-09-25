"""Endpoints de servimento e persistência de imagens de produtos.

GET /api/uploads/produtos/{filename}      — serve imagem definitiva
GET /api/uploads/produtos/temp/{filename} — serve imagem temporária de catálogo
"""

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.config import get_settings

router = APIRouter(prefix="/api/uploads/produtos", tags=["uploads"])

_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _get_base_dir(request: Request) -> Path:
    settings = get_settings()
    return Path(getattr(settings, "product_images_dir", "./data/product_images"))


def _validar_nome_arquivo(filename: str) -> None:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Extensão de imagem não suportada.")


@router.get("/{filename}")
async def obter_imagem_produto(filename: str, request: Request):
    _validar_nome_arquivo(filename)
    base_dir = _get_base_dir(request)
    file_path = base_dir / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Imagem não encontrada.")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(file_path, media_type=media_type or "application/octet-stream")


@router.get("/temp/{filename}")
async def obter_imagem_temporaria(filename: str, request: Request):
    _validar_nome_arquivo(filename)
    base_dir = _get_base_dir(request)
    file_path = base_dir / "temp" / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Imagem temporária não encontrada.")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(file_path, media_type=media_type or "application/octet-stream")


def salvar_imagem_produto(
    content: bytes,
    original_filename: str,
    is_temp: bool = False,
    base_dir: Path | None = None,
) -> tuple[str, Path]:
    """Salva os bytes da imagem no disco local com nome UUID único.

    Retorna a URL relativa servida e o caminho absoluto do arquivo no disco.
    """
    settings = get_settings()
    target_dir = base_dir or Path(getattr(settings, "product_images_dir", "./data/product_images"))
    if is_temp:
        target_dir = target_dir / "temp"
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        suffix = ".png"

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest_path = target_dir / unique_name
    dest_path.write_bytes(content)

    url_prefix = "/api/uploads/produtos/temp" if is_temp else "/api/uploads/produtos"
    return f"{url_prefix}/{unique_name}", dest_path
