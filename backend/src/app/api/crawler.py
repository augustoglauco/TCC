"""Endpoints HTTP do crawler de páginas do RAG (R4, Fase 2) — dispara um
crawl a partir de uma URL semente, e gerencia a fila de revisão de páginas
cuja classificação de domínio ficou abaixo do limiar de confiança. Ver
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.

# MVP: sem autenticação (mesma decisão do restante de `app.api.rag`) e
execução síncrona do `/run` — sem fila de background nem agendamento.
"""

import logging
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import (
    get_db_session,
    get_embedder_registry,
    get_qdrant_client,
    get_uploads_dir,
)
from app.db.models import CrawlerPendingPage
from app.models.crawler import (
    ApprovedPageResponse,
    ApprovePendingPageRequest,
    CrawlRunRequest,
    CrawlRunResponse,
    PendingPageResponse,
)
from app.rag.collections_registry import get_active_collection
from app.rag.crawler import crawl
from app.rag.crawler_classifier import classify_page
from app.rag.crawler_ingest import ingest_or_queue, replace_previous_ingestion
from app.rag.crawler_pending import delete_pending_page, get_pending_page, list_pending_pages
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag/crawler", tags=["crawler"])

_TEXT_SNIPPET_CHARS = 300

# Falhas ao classificar/ingerir uma página específica não abortam o resto do
# crawl (spec §5) — capturadas aqui e reportadas em `errors`.
_ERROS_POR_PAGINA = (RAGConnectionError, httpx.HTTPError, SQLAlchemyError)


def _to_pending_response(page: CrawlerPendingPage) -> PendingPageResponse:
    return PendingPageResponse(
        id=page.id,
        url=page.url,
        text_snippet=page.extracted_text[:_TEXT_SNIPPET_CHARS],
        domain_proposed=page.domain_proposed,
        confidence=page.confidence,
        created_at=page.created_at,
    )


@router.post("/run", response_model=CrawlRunResponse)
async def run_crawler(
    body: CrawlRunRequest,
    request: Request,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> CrawlRunResponse:
    collection = await get_active_collection(session)
    if collection is None:
        raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    max_pages = body.max_pages or request.app.state.crawler_max_pages_default
    confidence_threshold = request.app.state.crawler_confidence_threshold
    embedder = embedders.get(collection.embedding_model)

    result = await crawl(
        request.app.state.crawler_http_client, str(body.url), body.depth, max_pages
    )

    auto_ingested: list[str] = []
    queued: list[str] = []
    errors = list(result.errors)

    for page in result.pages:
        try:
            classification = await classify_page(request.app.state.external_client, page.text)
            outcome = await ingest_or_queue(
                session,
                qdrant,
                collection,
                embedder,
                uploads_dir,
                page.url,
                page.text,
                classification,
                confidence_threshold,
            )
        except _ERROS_POR_PAGINA as exc:
            logger.error(
                "crawler_pagina_indisponivel",
                extra={
                    "crawler": {
                        "event": "crawler_pagina_indisponivel",
                        "url": page.url,
                        "erro": str(exc),
                    }
                },
            )
            errors.append(page.url)
            continue

        if outcome == "ingested":
            auto_ingested.append(page.url)
        else:
            queued.append(page.url)

    return CrawlRunResponse(
        pages_visited=len(result.pages), auto_ingested=auto_ingested, queued=queued, errors=errors
    )


@router.get("/pending", response_model=list[PendingPageResponse])
async def get_pending(session: AsyncSession = Depends(get_db_session)) -> list[PendingPageResponse]:
    pages = await list_pending_pages(session)
    return [_to_pending_response(page) for page in pages]


@router.post("/pending/{page_id}/approve", response_model=ApprovedPageResponse)
async def approve_pending(
    page_id: UUID,
    body: ApprovePendingPageRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> ApprovedPageResponse:
    page = await get_pending_page(session, page_id)
    if page is None:
        raise HTTPException(status_code=404, detail="Página pendente não encontrada.")

    collection = await get_active_collection(session)
    if collection is None:
        raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    embedder = embedders.get(collection.embedding_model)
    try:
        await replace_previous_ingestion(session, qdrant, collection, page.url)
        documento = await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename=page.url,
            content=page.extracted_text.encode("utf-8"),
            domain=body.domain,
            session=session,
            origin="crawler",
        )
    except RAGConnectionError as exc:
        logger.error(
            "crawler_approve_indisponivel",
            extra={
                "crawler": {
                    "event": "crawler_approve_indisponivel",
                    "url": page.url,
                    "erro": str(exc),
                }
            },
        )
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
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

    await delete_pending_page(session, page_id)
    return ApprovedPageResponse(url=page.url, domain=body.domain, chunks=documento.chunk_count)


@router.post("/pending/{page_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_pending(page_id: UUID, session: AsyncSession = Depends(get_db_session)) -> None:
    deleted = await delete_pending_page(session, page_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Página pendente não encontrada.")
