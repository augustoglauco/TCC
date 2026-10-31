"""Registro de documentos ingeridos no RAG (R4, além do MVP) — CRUD sobre
`app.db.models.RagDocument`.

Ver docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md e
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3.
"""

import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagDocument

# O arquivo de download é gravado como `<id>_download_<nome>`; o nome original
# (o que o cliente vê) é o que vem depois do marcador.
DOWNLOAD_MARKER = "_download_"


def download_filename(document: RagDocument) -> str | None:
    """Nome do arquivo de download associado ao documento, ou `None` se não há."""
    if not document.download_path:
        return None
    return Path(document.download_path).name.split(DOWNLOAD_MARKER, 1)[-1]


def arquivos_em_disco(document: RagDocument) -> list[Path]:
    """Caminhos gravados do documento (ingerido e de download), para apagar."""
    caminhos = (document.storage_path, document.download_path)
    return [Path(caminho) for caminho in caminhos if caminho]


async def create_document(
    session: AsyncSession,
    *,
    document_id: str,
    collection_id: uuid.UUID,
    filename: str,
    domain: str,
    chunk_count: int,
    storage_path: str | None,
    origin: str,
    download_path: str | None = None,
) -> RagDocument:
    document = RagDocument(
        id=uuid.UUID(document_id),
        collection_id=collection_id,
        filename=filename,
        domain=domain,
        chunk_count=chunk_count,
        storage_path=storage_path,
        download_path=download_path,
        origin=origin,
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


async def list_documents(session: AsyncSession) -> list[RagDocument]:
    result = await session.execute(select(RagDocument).order_by(RagDocument.created_at.desc()))
    return list(result.scalars().all())


async def list_documents_by_collection(
    session: AsyncSession, collection_id: uuid.UUID
) -> list[RagDocument]:
    result = await session.execute(
        select(RagDocument).where(RagDocument.collection_id == collection_id)
    )
    return list(result.scalars().all())


async def count_documents_by_collection(session: AsyncSession) -> dict[uuid.UUID, int]:
    result = await session.execute(
        select(RagDocument.collection_id, func.count()).group_by(RagDocument.collection_id)
    )
    return dict(result.all())


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    document = await session.get(RagDocument, uuid.UUID(document_id))
    if document is None:
        return False
    await session.delete(document)
    await session.commit()
    return True
