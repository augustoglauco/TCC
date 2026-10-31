"""Ingestão (ou enfileiramento) de páginas crawleadas no RAG (R4, Fase 2) —
aplica o gate de confiança e o passo de dedup-por-URL descritos em
docs/superpowers/specs/2026-09-19-crawler-paginas-design.md §1, §3.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument
from app.models.rag import RagDocumentOrigin
from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_pending import upsert_pending_page
from app.rag.qdrant_client import QdrantRAGClient
from app.rag.registry import delete_document

_CRAWLER_ORIGIN: RagDocumentOrigin = "crawler"


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


async def queue_page(
    session: AsyncSession,
    collection: RagCollection,
    url: str,
    text: str,
    classification: PageClassification,
) -> None:
    """Põe a página na fila de revisão (`crawler_pending_pages`), fora do RAG
    até alguém aprovar. O LLM só sugere o domínio (`classification`): mesmo com
    confiança alta nada é ingerido sozinho; quem decide domínio e collection é
    o administrador. Recrawlear a mesma URL ainda pendente atualiza a linha."""
    await upsert_pending_page(
        session,
        url=url,
        extracted_text=text,
        domain_proposed=classification.domain,
        confidence=classification.confidence,
        collection_id=collection.id,
    )
