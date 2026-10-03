"""Testes do `AdminAllCollectionsRagClient` (decisão de 2026-09-30,
docs/ARCHITECTURE.md §6): o Admin, no chat, busca a collection `chat` ativa
+ toda `purpose="mcp_b2b"` + toda `purpose="admin"` — nunca uma `chat` não
ativa (artefato de comparação do admin em `/admin/ingestao`).
"""

import uuid

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.rag.admin_all_collections_client import AdminAllCollectionsRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.embeddings import TextEmbedder
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

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


async def _cria_collection_com_conteudo(
    factory,
    qdrant: QdrantRAGClient,
    text_embedder: TextEmbedder,
    *,
    name: str,
    purpose: str,
    is_active: bool,
    conteudo: str,
    source: str,
    document_id: str,
) -> None:
    dimension = await text_embedder.get_dimension()
    async with factory() as session:
        session.add(
            RagCollection(
                id=uuid.uuid4(),
                name=name,
                embedding_model=text_embedder.model_name,
                vector_dimension=dimension,
                distance_metric="cosine",
                chunk_size=800,
                chunk_overlap=100,
                quantization_type="none",
                quantization_config={},
                payload_indexes=[],
                is_active=is_active,
                purpose=purpose,
                **_DEFAULT_HNSW,
            )
        )
        await session.commit()
    await qdrant.create_collection(
        name=name,
        vector_dimension=dimension,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await qdrant.upsert_chunks(
        name, text_embedder, [conteudo], source=source, domain="vendas", document_id=document_id
    )


async def test_admin_client_agrega_chat_ativa_mcp_b2b_e_admin(text_embedder: TextEmbedder):
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    for name, purpose, source in [
        ("chat", "chat", "publico.txt"),
        ("mcp_b2b", "mcp_b2b", "parceiro.txt"),
        ("admin", "admin", "admin_only.txt"),
    ]:
        await _cria_collection_com_conteudo(
            factory,
            qdrant,
            text_embedder,
            name=f"{name}_{uuid.uuid4().hex}",
            purpose=purpose,
            is_active=True,
            conteudo="conteúdo sobre o produto X",
            source=source,
            document_id=f"doc-{name}",
        )

    client = AdminAllCollectionsRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas", top_k=10)

    fontes = {doc.source for doc in resultado}
    assert fontes == {"publico.txt", "parceiro.txt", "admin_only.txt"}
    await engine.dispose()


async def test_admin_client_ignora_collections_inativas(text_embedder: TextEmbedder):
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    for name, purpose in [
        ("chat", "chat"),
        ("mcp_b2b", "mcp_b2b"),
        ("admin", "admin"),
    ]:
        await _cria_collection_com_conteudo(
            factory,
            qdrant,
            text_embedder,
            name=f"{name}_inativa_{uuid.uuid4().hex}",
            purpose=purpose,
            is_active=False,
            conteudo="conteúdo de comparação sobre o produto X",
            source=f"{name}.txt",
            document_id=f"doc-{name}",
        )

    client = AdminAllCollectionsRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas")

    assert resultado == []
    await engine.dispose()


class _FailingSessionFactory:
    def __call__(self) -> _FailingSessionFactory:
        return self

    async def __aenter__(self):
        raise SQLAlchemyError("conexão com o banco indisponível")

    async def __aexit__(self, *exc_info) -> bool:
        return False


async def test_admin_client_com_erro_no_postgres_levanta_rag_connection_error():
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))
    client = AdminAllCollectionsRagClient(qdrant, _FailingSessionFactory(), EmbedderRegistry())

    with pytest.raises(RAGConnectionError):
        await client.search("qualquer coisa", domain="vendas")
