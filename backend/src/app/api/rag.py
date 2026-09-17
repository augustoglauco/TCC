"""Endpoints HTTP de documentos do RAG (R4, além do MVP): upload, listagem,
exclusão e reingestão em outra collection.

# MVP: sem autenticação (rotas não listadas na navegação pública do
# frontend, mas não protegidas por login). `upload_document` complementa,
# sem substituir, o script de ingestão em lote
# (`backend/scripts/ingest_sample_docs.py`). Mesma limitação de
# `app.rag.qdrant_client.upsert_chunks`: sem deduplicação/reingestão
# incremental automática. Decisão registrada em `docs/ARCHITECTURE.md` §5.
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import (
    get_db_session,
    get_embedder_registry,
    get_qdrant_client,
    get_uploads_dir,
)
from app.db.models import RagDocument
from app.models.rag import (
    DocumentIngestResponse,
    DocumentRegistryResponse,
    RagDomain,
    ReingestRequest,
)
from app.rag.collections_registry import get_active_collection, get_collection, list_collections
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import SUPPORTED_SUFFIXES, ingest_bytes, reingest_document
from app.rag.pdf_extract import PdfExtractionError
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document, list_documents
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["rag"])


def _document_to_response(document: RagDocument, collection_name: str) -> DocumentRegistryResponse:
    return DocumentRegistryResponse(
        id=document.id,
        filename=document.filename,
        domain=document.domain,
        chunk_count=document.chunk_count,
        collection_id=document.collection_id,
        collection_name=collection_name,
        origin=document.origin,
        created_at=document.created_at,
    )


@router.post("/documents", response_model=DocumentIngestResponse)
async def upload_document(
    domain: RagDomain = Form(...),
    file: UploadFile = File(...),
    collection_id: UUID | None = Form(None),
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentIngestResponse:
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Formato não suportado: '{suffix or filename}'. "
                f"Use um destes: {sorted(SUPPORTED_SUFFIXES)}."
            ),
        )

    if collection_id is not None:
        collection = await get_collection(session, collection_id)
        if collection is None:
            raise HTTPException(status_code=404, detail="Collection não encontrada.")
    else:
        collection = await get_active_collection(session)
        if collection is None:
            raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    embedder = embedders.get(collection.embedding_model)
    content = await file.read()
    try:
        documento = await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename,
            content,
            domain,
            session=session,
            origin="upload",
        )
    except RAGConnectionError as exc:
        logger.error(
            "rag_upload_indisponivel",
            extra={"rag": {"event": "rag_upload_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (UnicodeDecodeError, PdfExtractionError) as exc:
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
                "Serviço de registro de documentos temporariamente indisponível, tente novamente."
            ),
        ) from exc

    return DocumentIngestResponse(filename=filename, domain=domain, chunks=documento.chunk_count)


@router.get("/documents", response_model=list[DocumentRegistryResponse])
async def get_documents(
    session: AsyncSession = Depends(get_db_session),
) -> list[DocumentRegistryResponse]:
    try:
        documentos = await list_documents(session)
        collections = await list_collections(session)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, tente novamente."
            ),
        ) from exc
    nomes = {collection.id: collection.name for collection in collections}
    return [
        _document_to_response(documento, nomes.get(documento.collection_id, "?"))
        for documento in documentos
    ]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document_endpoint(
    document_id: UUID,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    document = await session.get(RagDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    collection = await get_collection(session, document.collection_id)
    if collection is not None:
        try:
            await qdrant.delete_by_document_id(collection.name, str(document_id))
        except RAGConnectionError as exc:
            logger.error(
                "rag_delete_indisponivel",
                extra={"rag": {"event": "rag_delete_indisponivel", "erro": str(exc)}},
            )
            raise HTTPException(
                status_code=503,
                detail="Serviço de RAG temporariamente indisponível, tente novamente.",
            ) from exc

    if document.storage_path is not None:
        Path(document.storage_path).unlink(missing_ok=True)

    try:
        await delete_document(session, str(document_id))
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, tente novamente."
            ),
        ) from exc


@router.post("/documents/{document_id}/reingest", response_model=DocumentRegistryResponse)
async def reingest_document_endpoint(
    document_id: UUID,
    body: ReingestRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentRegistryResponse:
    source_document = await session.get(RagDocument, document_id)
    if source_document is None:
        raise HTTPException(status_code=404, detail="Documento não encontrado.")

    target_collection = await get_collection(session, body.target_collection_id)
    if target_collection is None:
        raise HTTPException(status_code=404, detail="Collection destino não encontrada.")

    if target_collection.id == source_document.collection_id:
        raise HTTPException(
            status_code=409,
            detail="A collection destino não pode ser a mesma do documento de origem.",
        )

    if source_document.storage_path is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Documento sem arquivo salvo (ingerido antes desta funcionalidade existir) "
                "— não é possível reingerir."
            ),
        )

    embedder = embedders.get(target_collection.embedding_model)
    try:
        novo_documento = await reingest_document(
            qdrant, embedder, source_document, target_collection, session
        )
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc
    except (FileNotFoundError, OSError) as exc:
        # Achado #4 da revisão final: o arquivo original pode ter sido
        # apagado (DELETE concorrente do documento, limpeza externa de
        # disco) entre a checagem de `storage_path is None` acima e a
        # leitura de fato dentro de `reingest_document` — sem isso, o
        # `read_bytes()` cru vira um 500 em vez de um erro HTTP limpo.
        logger.warning(
            "rag_reingest_arquivo_ausente document_id=%s storage_path=%s",
            document_id,
            source_document.storage_path,
        )
        raise HTTPException(
            status_code=404,
            detail=(
                "Arquivo original do documento não foi encontrado em disco — não é possível "
                "reingerir."
            ),
        ) from exc
    except SQLAlchemyError as exc:
        logger.error(
            "rag_registro_indisponivel",
            extra={"rag": {"event": "rag_registro_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de documentos temporariamente indisponível, tente novamente."
            ),
        ) from exc

    return _document_to_response(novo_documento, target_collection.name)
