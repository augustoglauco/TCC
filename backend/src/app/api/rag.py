"""Endpoints HTTP do registro de documentos do RAG (R4, além do MVP).

# MVP: sem autenticação (rotas não listadas na navegação pública do
# frontend, mas não protegidas por login). `upload_document` complementa,
# sem substituir, o script de ingestão em lote
# (`backend/scripts/ingest_sample_docs.py`). Mesma limitação de
# `app.rag.qdrant_client.upsert_chunks`: sem deduplicação/reingestão
# incremental. Decisão registrada em `docs/ARCHITECTURE.md` §5.
"""

import logging
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pypdf.errors import PyPdfError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import DocumentIngestResponse, DocumentRegistryResponse, RagDomain
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document, list_documents
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


def get_rag_client(request: Request) -> QdrantRAGClient:
    return request.app.state.rag_client


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db_sessionmaker() as session:
        yield session


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    rag_client: QdrantRAGClient = Depends(get_rag_client),
    session: AsyncSession = Depends(get_db_session),
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
        documento = await ingest_bytes(
            rag_client, filename, content, domain, session=session, origin="upload"
        )
    except RAGConnectionError as exc:
        logger.error(
            "rag_upload_indisponivel",
            extra={"rag": {"event": "rag_upload_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (UnicodeDecodeError, PyPdfError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Não foi possível extrair texto de '{filename}': {exc}"
        ) from exc
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, "
                "tente novamente."
            ),
        ) from exc

    return DocumentIngestResponse(filename=filename, domain=domain, chunks=documento.chunk_count)


@router.get("/documents", response_model=list[DocumentRegistryResponse])
async def get_documents(
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentRegistryResponse]:
    try:
        documentos = await list_documents(session)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, "
                "tente novamente."
            ),
        ) from exc
    return [DocumentRegistryResponse.model_validate(documento) for documento in documentos]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: UUID,
    rag_client: QdrantRAGClient = Depends(get_rag_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await rag_client.delete_by_document_id(str(document_id))
    except RAGConnectionError as exc:
        logger.error(
            "rag_delete_indisponivel",
            extra={"rag": {"event": "rag_delete_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    try:
        removido = await delete_document(session, str(document_id))
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, "
                "tente novamente."
            ),
        ) from exc
    if not removido:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
