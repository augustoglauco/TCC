"""Registro de perfis de collection do RAG (Entregas B+C+D, além do MVP) —
CRUD sobre `app.db.models.RagCollection`.

Ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §3.
Perfis são imutáveis depois de criados — não há função de "update" aqui de
propósito (mudar um parâmetro é criar uma nova collection).
"""

import uuid

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RagCollection, RagDocument


class CollectionActiveError(Exception):
    """Levantada ao tentar excluir a collection atualmente ativa."""


async def create_collection(
    session: AsyncSession,
    *,
    name: str,
    embedding_model: str,
    vector_dimension: int,
    distance_metric: str,
    chunk_size: int,
    chunk_overlap: int,
    hnsw_m: int,
    hnsw_ef_construct: int,
    hnsw_full_scan_threshold: int,
    hnsw_max_indexing_threads: int,
    hnsw_on_disk: bool,
    hnsw_payload_m: int | None,
    quantization_type: str,
    quantization_config: dict,
    payload_indexes: list,
    is_active: bool = False,
) -> RagCollection:
    collection = RagCollection(
        id=uuid.uuid4(),
        name=name,
        embedding_model=embedding_model,
        vector_dimension=vector_dimension,
        distance_metric=distance_metric,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        hnsw_m=hnsw_m,
        hnsw_ef_construct=hnsw_ef_construct,
        hnsw_full_scan_threshold=hnsw_full_scan_threshold,
        hnsw_max_indexing_threads=hnsw_max_indexing_threads,
        hnsw_on_disk=hnsw_on_disk,
        hnsw_payload_m=hnsw_payload_m,
        quantization_type=quantization_type,
        quantization_config=quantization_config,
        payload_indexes=payload_indexes,
        is_active=is_active,
    )
    session.add(collection)
    await session.commit()
    await session.refresh(collection)
    return collection


async def list_collections(session: AsyncSession) -> list[RagCollection]:
    result = await session.execute(select(RagCollection).order_by(RagCollection.created_at.desc()))
    return list(result.scalars().all())


async def get_collection(session: AsyncSession, collection_id: uuid.UUID) -> RagCollection | None:
    return await session.get(RagCollection, collection_id)


async def get_collection_by_name(session: AsyncSession, name: str) -> RagCollection | None:
    result = await session.execute(select(RagCollection).where(RagCollection.name == name))
    return result.scalars().first()


async def get_active_collection(session: AsyncSession) -> RagCollection | None:
    result = await session.execute(select(RagCollection).where(RagCollection.is_active.is_(True)))
    return result.scalars().first()


async def activate_collection(session: AsyncSession, collection_id: uuid.UUID) -> bool:
    collection = await session.get(RagCollection, collection_id)
    if collection is None:
        return False
    await session.execute(update(RagCollection).values(is_active=False))
    collection.is_active = True
    await session.commit()
    return True


async def delete_collection(session: AsyncSession, collection_id: uuid.UUID) -> bool:
    """Remove a collection e, em cascata, os documentos registrados nela
    (ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md
    §6.1). A remoção da collection real no Qdrant e dos arquivos em disco é
    responsabilidade de quem chama esta função (`app.api.rag_collections`),
    feita ANTES desta chamada — ver ordem "Qdrant → arquivos → Postgres" na
    spec.
    """
    collection = await session.get(RagCollection, collection_id)
    if collection is None:
        return False
    if collection.is_active:
        raise CollectionActiveError(str(collection_id))
    await session.execute(delete(RagDocument).where(RagDocument.collection_id == collection_id))
    await session.delete(collection)
    await session.commit()
    return True
