"""Registro de documentos ingeridos no RAG (R4, além do MVP) — CRUD sobre
`app.db.models.RagDocument`.

Ver docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument


async def create_document(
    session: AsyncSession,
    *,
    document_id: str,
    filename: str,
    domain: str,
    chunk_count: int,
    embedding_model: str,
    chunk_size: int,
    chunk_overlap: int,
    origin: str,
) -> RagDocument:
    document = RagDocument(
        id=uuid.UUID(document_id),
        filename=filename,
        domain=domain,
        chunk_count=chunk_count,
        embedding_model=embedding_model,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        origin=origin,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(session: AsyncSession) -> list[RagDocument]:
    result = await session.execute(select(RagDocument).order_by(RagDocument.created_at.desc()))
    return list(result.scalars().all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    document = await session.get(RagDocument, uuid.UUID(document_id))
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
