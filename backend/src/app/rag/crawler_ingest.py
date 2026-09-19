"""Ingestão (ou enfileiramento) de páginas crawleadas no RAG (R4, Fase 2) —
aplica o gate de confiança e o passo de dedup-por-URL descritos em
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md §1, §3.
"""

from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument
from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_pending import upsert_pending_page
from app.rag.embeddings import TextEmbedder
from app.rag.ingest import ingest_bytes
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document

_CRAWLER_ORIGIN = "crawler"


async def replace_previous_ingestion(
    session: AsyncSession,
    qdrant: QdrantRAGClient,
    collection: RagCollection,
    url: str,
) -> None:
    """Remove pontos + registro de uma ingestão anterior da mesma `url`
    nesta `collection`, se existir — evita duplicar pontos no Qdrant ao
    recrawlear (spec §3). No-op se a URL nunca foi ingerida antes."""
    result = await session.execute(
        select(RagDocument).where(
            RagDocument.filename == url,
            RagDocument.collection_id == collection.id,
            RagDocument.origin == _CRAWLER_ORIGIN,
        )
    )
    documento_anterior = result.scalars().first()
    if documento_anterior is None:
        return
    await qdrant.delete_by_document_id(collection.name, str(documento_anterior.id))
    await delete_document(session, str(documento_anterior.id))


async def ingest_or_queue(
    session: AsyncSession,
    qdrant: QdrantRAGClient,
    collection: RagCollection,
    embedder: TextEmbedder,
    uploads_dir: Path,
    url: str,
    text: str,
    classification: PageClassification,
    confidence_threshold: float,
) -> Literal["ingested", "queued"]:
    """Aplica o gate de confiança: `confidence >= confidence_threshold`
    ingere direto (com dedup-por-URL antes); abaixo do limiar, upsert na
    fila de revisão (`crawler_pending_pages`), fora do RAG até aprovação."""
    if classification.confidence >= confidence_threshold:
        await replace_previous_ingestion(session, qdrant, collection, url)
        await ingest_bytes(
            qdrant,
            embedder,
            collection,
            uploads_dir,
            filename=url,
            content=text.encode("utf-8"),
            domain=classification.domain,
            session=session,
            origin=_CRAWLER_ORIGIN,
        )
        return "ingested"

    await upsert_pending_page(
        session,
        url=url,
        extracted_text=text,
        domain_proposed=classification.domain,
        confidence=classification.confidence,
    )
    return "queued"
