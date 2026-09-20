"""Endpoints de busca multimodal por imagem via CLIP (R6).

POST /api/rag/images        — ingere uma imagem no catálogo visual
POST /api/rag/images/search — busca por imagem ou texto
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.models.rag import RagDomain
from app.ocr.image_processor import detect_image_format
from app.rag.clip_embedder import ClipEmbedder
from app.rag.image_search import ClipImageStore, ImageSearchResult
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag/images", tags=["rag-images"])

_ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}


def _get_clip_store(request: Request) -> ClipImageStore:
    return request.app.state.clip_image_store


def _get_clip_embedder(request: Request) -> ClipEmbedder:
    return request.app.state.clip_embedder


def _validate_image(content: bytes, filename: str) -> None:
    fmt = detect_image_format(content)
    if fmt not in _ACCEPTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{filename}'. Use PNG, JPG ou WEBP.",
        )


@router.post("", status_code=201)
async def ingest_image(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    store: ClipImageStore = Depends(_get_clip_store),
    embedder: ClipEmbedder = Depends(_get_clip_embedder),
) -> dict:
    """Ingere uma imagem (PNG/JPG/WEBP) no catálogo visual CLIP."""
    content = await file.read()
    _validate_image(content, file.filename or "")
    try:
        image_id = await store.upsert_image(
            embedder, content, filename=file.filename or "", domain=domain
        )
    except RAGConnectionError as exc:
        raise HTTPException(status_code=503, detail="Serviço de RAG indisponível.") from exc
    return {"image_id": image_id, "filename": file.filename, "domain": domain}


@router.post("/search", response_model=list[ImageSearchResult])
async def search_images(
    query: str | None = Form(default=None),
    domain: RagDomain | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    store: ClipImageStore = Depends(_get_clip_store),
    embedder: ClipEmbedder = Depends(_get_clip_embedder),
) -> list[ImageSearchResult]:
    """Busca imagens similares por imagem de consulta ou descrição textual.

    Envie `file` (imagem) OU `query` (texto) — pelo menos um é obrigatório.
    """
    if file is None and not query:
        raise HTTPException(status_code=422, detail="Informe 'file' (imagem) ou 'query' (texto).")
    try:
        if file is not None:
            content = await file.read()
            _validate_image(content, file.filename or "")
            return await store.search_by_image(embedder, content, domain=domain)
        return await store.search_by_text(embedder, query, domain=domain)  # type: ignore[arg-type]
    except RAGConnectionError as exc:
        raise HTTPException(status_code=503, detail="Serviço de RAG indisponível.") from exc
