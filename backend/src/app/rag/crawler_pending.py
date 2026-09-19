"""CRUD da fila de revisão de páginas crawleadas (R4, Fase 2) — sobre
`app.db.models.CrawlerPendingPage`. Mesmo padrão de `app.rag.registry`.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CrawlerPendingPage


async def upsert_pending_page(
    session: AsyncSession,
    *,
    url: str,
    extracted_text: str,
    domain_proposed: str,
    confidence: float,
) -> CrawlerPendingPage:
    """Cria a linha pendente para `url`, ou atualiza a existente (mesma URL
    recrawleada antes de alguém revisar) — evita fila duplicada pra mesma
    URL (spec §"Dedup por URL")."""
    result = await session.execute(select(CrawlerPendingPage).where(CrawlerPendingPage.url == url))
    existing = result.scalars().first()
    if existing is not None:
        existing.extracted_text = extracted_text
        existing.domain_proposed = domain_proposed
        existing.confidence = confidence
        await session.commit()
        await session.refresh(existing)
        return existing

    page = CrawlerPendingPage(
        id=uuid.uuid4(),
        url=url,
        extracted_text=extracted_text,
        domain_proposed=domain_proposed,
        confidence=confidence,
    )
    session.add(page)
    await session.commit()
    await session.refresh(page)
    return page


async def list_pending_pages(session: AsyncSession) -> list[CrawlerPendingPage]:
    result = await session.execute(
        select(CrawlerPendingPage).order_by(CrawlerPendingPage.created_at.desc())
    )
    return list(result.scalars().all())


async def get_pending_page(session: AsyncSession, page_id: uuid.UUID) -> CrawlerPendingPage | None:
    return await session.get(CrawlerPendingPage, page_id)


async def delete_pending_page(session: AsyncSession, page_id: uuid.UUID) -> bool:
    page = await session.get(CrawlerPendingPage, page_id)
    if page is None:
        return False
    await session.delete(page)
    await session.commit()
    return True
