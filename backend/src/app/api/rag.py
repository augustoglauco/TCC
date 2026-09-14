"""Endpoint HTTP de upload para ingestão de documentos no RAG (R4).

# MVP: upload síncrono e sem autenticação (rota não listada na navegação
# pública do frontend, mas não protegida por login) — complementa, sem
# substituir, o script de ingestão em lote
# (`backend/scripts/ingest_sample_docs.py`). Mesma limitação de
# `app.rag.qdrant_client.upsert_chunks`: sem deduplicação/reingestão
# incremental. Decisão registrada em `docs/ARCHITECTURE.md` §5.
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pypdf.errors import PyPdfError

from app.api.chat import get_rag_client
from app.models.rag import DocumentIngestResponse, RagDomain
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    rag_client: QdrantRAGClient = Depends(get_rag_client),
) -> DocumentIngestResponse:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: '{suffix or filename}'. "
            f"Use um destes: {sorted(SUPPORTED_SUFFIXES)}.",
        )

    content = await file.read()
    try:
        chunks = await ingest_bytes(rag_client, filename, content, domain)
    except RAGConnectionError as exc:
        logger.error(
            "rag_upload_indisponivel",
            extra={"rag": {"event": "rag_upload_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (UnicodeDecodeError, PyPdfError) as exc:
        # Extensão suportada (.txt/.md/.pdf) não garante conteúdo válido —
        # ex.: texto que não é UTF-8 (comum em .txt salvo como Windows-1252)
        # ou PDF corrompido/criptografado. Sem isso, `_extract_text` deixa
        # a exceção subir crua e vira 500 em vez de um erro de validação.
        raise HTTPException(
            status_code=400, detail=f"Não foi possível extrair texto de '{filename}': {exc}"
        ) from exc

    return DocumentIngestResponse(filename=filename, domain=domain, chunks=chunks)
