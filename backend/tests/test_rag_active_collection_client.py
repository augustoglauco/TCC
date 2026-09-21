import uuid

import pytest
from qdrant_client import AsyncQdrantClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base, RagCollection
from app.rag.active_collection_client import ActiveCollectionRagClient
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
    """Cria a linha em `rag_collections`, a collection no Qdrant e insere um
    chunk — usado pelos testes de isolamento entre chat e MCP B2B."""
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


async def test_chat_nao_recupera_conteudo_de_collection_mcp_b2b(text_embedder: TextEmbedder):
    """Isolamento: com uma collection `chat` ativa e uma `mcp_b2b` separada
    com conteúdo, a busca do chat retorna só o conteúdo da `chat` — o
    documento da `mcp_b2b` nunca aparece (ver
    docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §4/§7)."""
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"chat_{uuid.uuid4().hex}",
        purpose="chat",
        is_active=True,
        conteudo="conteúdo público sobre o produto X",
        source="publico.txt",
        document_id="doc-chat",
    )
    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"mcp_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=False,
        conteudo="conteúdo restrito ao produto X para parceiros",
        source="restrito.txt",
        document_id="doc-mcp",
    )

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas")

    fontes = {doc.source for doc in resultado}
    assert "publico.txt" in fontes
    assert "restrito.txt" not in fontes
    await engine.dispose()


async def test_search_falha_fechado_se_collection_ativa_for_mcp_b2b(text_embedder: TextEmbedder):
    """Defesa em profundidade: mesmo que a invariante seja quebrada e uma
    collection `mcp_b2b` acabe marcada como ativa, a busca do chat devolve
    vazio em vez de servir conteúdo restrito (guarda em
    `ActiveCollectionRagClient.search`)."""
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    await _cria_collection_com_conteudo(
        factory,
        qdrant,
        text_embedder,
        name=f"mcp_{uuid.uuid4().hex}",
        purpose="mcp_b2b",
        is_active=True,  # estado impossível pela API, forçado aqui de propósito
        conteudo="conteúdo restrito ao produto X",
        source="restrito.txt",
        document_id="doc-mcp",
    )

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("produto X", domain="vendas")

    assert resultado == []
    await engine.dispose()


async def test_search_sem_collection_ativa_retorna_lista_vazia():
    engine, factory = await _engine_e_sessionmaker_vazios()
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))

    client = ActiveCollectionRagClient(qdrant, factory, EmbedderRegistry())
    resultado = await client.search("qualquer coisa", domain="vendas")

    assert resultado == []
    await engine.dispose()


class _FailingSessionFactory:
    """Dublê de `async_sessionmaker` cuja sessão levanta `SQLAlchemyError` ao
    ser aberta — simula um Postgres indisponível no caminho do chat (ver
    finding #4 da revisão final)."""

    def __call__(self) -> "_FailingSessionFactory":
        return self

    async def __aenter__(self):
        raise SQLAlchemyError("conexão com o banco indisponível")

    async def __aexit__(self, *exc_info) -> bool:
        return False


async def test_search_com_erro_no_postgres_levanta_rag_connection_error():
    qdrant = QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))
    client = ActiveCollectionRagClient(qdrant, _FailingSessionFactory(), EmbedderRegistry())

    with pytest.raises(RAGConnectionError):
        await client.search("qualquer coisa", domain="vendas")
