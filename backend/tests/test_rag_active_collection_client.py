import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import QdrantRAGClient

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_search_usa_a_collection_marcada_como_ativa(text_embedder: TextEmbedder):
    engine, factory = await _engine_e_sessionmaker_vazios()
    collection_name = f"test_{uuid.uuid4().hex}"
    dimension = await text_embedder.get_dimension()

    async with factory() as session:
        session.add(
            RagCollection(
                id=uuid.uuid4(),
                name=collection_name,
                embedding_model=text_embedder.model_name,
                vector_dimension=dimension,
                distance_metric="cosine",
                chunk_size=800,
                chunk_overlap=100,
                quantization_type="none",
                quantization_config={},
                payload_indexes=[],
                is_active=True,
                **_DEFAULT_HNSW,
            )
        )
        await session.commit()

    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))
    await qdrant.create_collection(
        name=collection_name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await qdrant.upsert_chunks(
        collection_name,
        text_embedder,
        ["conteúdo sobre o produto X"],
        source="a.txt",
        domain="vendas",
        document_id="doc-1",
    )

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas")

    assert len(resultado) == 1
    assert resultado[0].source == "a.txt"
    await engine.dispose()


async def test_search_sem_collection_ativa_retorna_lista_vazia():
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("qualquer coisa", domain="vendas")

    assert resultado == []
    await engine.dispose()
