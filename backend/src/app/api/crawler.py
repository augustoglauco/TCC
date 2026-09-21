"""Endpoints HTTP do crawler de páginas do RAG (R4, Fase 2) — dispara um
crawl a partir de uma URL semente, e gerencia a fila de revisão de páginas
cuja classificação de domínio ficou abaixo do limiar de confiança. Ver
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.

# MVP: sem autenticação (mesma decisão do restante de `app.api.rag`) e
execução síncrona do `/run` — sem fila de background nem agendamento.
"""

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import HttpUrl, TypeAdapter, ValidationError
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
from app.rag.crawler import crawl, crawl_stream
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

# Valida `url` do endpoint SSE (GET, query param) com a mesma regra do
# `CrawlRunRequest.url` (HttpUrl) — EventSource só faz GET, então não dá para
# reaproveitar o body Pydantic do POST.
_HTTP_URL_ADAPTER = TypeAdapter(HttpUrl)


def _sse(event: str, data: dict) -> str:
    """Formata um bloco SSE (mesmo helper de `app.api.chat`)."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
            # Achado #2 da revisão final: sem o rollback, um `SQLAlchemyError`
            # (ex.: falha no commit) deixa a `AsyncSession` em estado de
            # pending-rollback — toda operação seguinte na mesma sessão passa
            # a levantar `PendingRollbackError` (também um `SQLAlchemyError`),
            # convertendo silenciosamente todas as páginas seguintes deste
            # crawl em "erro", mesmo sem falha própria delas. Chamado
            # incondicionalmente (é um no-op seguro quando não há transação
            # pendente) para cobrir também os outros erros de `_ERROS_POR_PAGINA`.
            await session.rollback()
            # `rollback()` expira todas as instâncias ORM anexadas à sessão
            # (inclusive `collection`, carregada uma única vez antes do loop
            # e reutilizada em toda página) — sem o refresh, o acesso a um
            # atributo de `collection` na próxima iteração dispara um lazy
            # load implícito que o `AsyncSession` não suporta
            # (`MissingGreenlet`), quebrando a página seguinte mesmo depois
            # do rollback já ter "limpo" a sessão.
            await session.refresh(collection)
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


@router.get("/run/stream")
async def run_crawler_stream(
    request: Request,
    url: str = Query(..., description="URL semente do crawl."),
    depth: int = Query(..., ge=0),
    max_pages: int | None = Query(default=None, ge=1),
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    uploads_dir: Path = Depends(get_uploads_dir),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Versão SSE de `POST /run` — emite progresso em tempo real, um evento
    por página, para que o frontend saiba que o crawl está vivo (e detecte
    travamento por ausência de eventos). Consumido via `EventSource`.

    Eventos: `visitando` (URL atual, heartbeat), `ingerida`, `enfileirada`,
    `erro` (por página) e `done` (resumo final). Mantido em paralelo ao
    `POST /run` clássico enquanto o novo fluxo é validado (será o único
    depois — decisão registrada em docs/ROADMAP.md).
    """
    try:
        seed_url = str(_HTTP_URL_ADAPTER.validate_python(url))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="URL semente inválida.") from exc

    collection = await get_active_collection(session)
    if collection is None:
        raise HTTPException(status_code=503, detail="Nenhuma collection ativa configurada.")

    effective_max_pages = max_pages or request.app.state.crawler_max_pages_default
    confidence_threshold = request.app.state.crawler_confidence_threshold
    embedder = embedders.get(collection.embedding_model)

    async def event_stream() -> AsyncIterator[str]:
        pages_visited = 0
        auto_ingested: list[str] = []
        queued: list[str] = []
        errors: list[str] = []

        try:
            async for evento in crawl_stream(
                request.app.state.crawler_http_client, seed_url, depth, effective_max_pages
            ):
                if evento.event == "visitando":
                    yield _sse("visitando", {"url": evento.url})
                    continue
                if evento.event == "erro":
                    errors.append(evento.url)
                    yield _sse("erro", {"url": evento.url})
                    continue

                # evento.event == "pagina"
                page = evento.page
                assert page is not None
                pages_visited += 1
                try:
                    classification = await classify_page(
                        request.app.state.external_client, page.text
                    )
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
                    # Mesmo tratamento do POST /run: rollback + refresh para
                    # não contaminar as páginas seguintes (ver comentário
                    # detalhado em `run_crawler`).
                    await session.rollback()
                    await session.refresh(collection)
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
                    yield _sse("erro", {"url": page.url})
                    continue

                if outcome == "ingested":
                    auto_ingested.append(page.url)
                    yield _sse("ingerida", {"url": page.url, "domain": classification.domain})
                else:
                    queued.append(page.url)
                    yield _sse("enfileirada", {"url": page.url, "domain": classification.domain})
        except Exception as exc:  # noqa: BLE001
            # Falha inesperada do próprio crawl (não de uma página): emite um
            # `error` para o cliente não ficar "pendurado" achando que travou.
            logger.exception("crawler_stream_falhou")
            yield _sse("error", {"detail": f"Falha no crawl: {exc}"})
            return

        yield _sse(
            "done",
            {
                "pages_visited": pages_visited,
                "auto_ingested": auto_ingested,
                "queued": queued,
                "errors": errors,
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
