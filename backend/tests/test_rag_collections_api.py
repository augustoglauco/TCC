import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from qdrant_client import AsyncQdrantClient

from app.api.rag_collections import router as rag_collections_router
from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


class _FakeEmbedderRegistry(EmbedderRegistry):
    """Sobrepõe `get` para devolver um embedder falso com dimensão fixa,
    sem baixar/carregar `sentence-transformers` de verdade nos testes de
    endpoint (isso já é coberto pelos testes reais de `embeddings.py`)."""

    def get(self, model_name: str):
        class _FakeEmbedder:
            async def get_dimension(self) -> int:
                return 384

        return _FakeEmbedder()


def _qdrant() -> QdrantRAGClient:
    return QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:"))


def _build_app(qdrant: QdrantRAGClient, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_collections_router)
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embedder_registry] = lambda: _FakeEmbedderRegistry()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


_PAYLOAD_MINIMO = {
    "name": "nova_collection",
    "embedding_model": "fake-embedding-model",
    "distance_metric": "cosine",
    "chunk_size": 800,
    "chunk_overlap": 100,
    "hnsw": {
        "m": 16,
        "ef_construct": 100,
        "full_scan_threshold": 10000,
        "max_indexing_threads": 0,
        "on_disk": False,
        "payload_m": None,
    },
    "quantization": {"type": "none"},
    "payload_indexes": [{"field": "domain", "schema_type": "keyword"}],
}


def test_criar_collection_grava_no_qdrant_e_no_registro(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post("/api/rag/collections", json=_PAYLOAD_MINIMO)

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "nova_collection"
    assert body["vector_dimension"] == 384
    assert body["is_active"] is False
    assert body["document_count"] == 0


async def test_criar_collection_com_nome_duplicado_retorna_409(db_session, active_collection):
    qdrant = _qdrant()
    await qdrant.create_collection(
        name=active_collection.name,
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))
    payload = {**_PAYLOAD_MINIMO, "name": active_collection.name}

    response = client.post("/api/rag/collections", json=payload)

    assert response.status_code == 409


def test_criar_collection_com_chunk_size_menor_que_overlap_retorna_422(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))
    payload = {**_PAYLOAD_MINIMO, "chunk_size": 100, "chunk_overlap": 200}

    response = client.post("/api/rag/collections", json=payload)

    assert response.status_code == 422


async def test_listar_collections_inclui_contagem_de_documentos(db_session, active_collection):
    from app.rag.registry import create_document

    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=active_collection.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.get("/api/rag/collections")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["document_count"] == 1
    assert body[0]["is_active"] is True


async def test_ativar_collection_troca_qual_esta_ativa(db_session, active_collection):
    from app.rag.collections_registry import create_collection

    outra = await create_collection(
        db_session,
        name="outra",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post(f"/api/rag/collections/{outra.id}/activate")

    assert response.status_code == 204
    body = client.get("/api/rag/collections").json()
    ativa = next(c for c in body if c["id"] == str(outra.id))
    assert ativa["is_active"] is True


def test_ativar_collection_inexistente_retorna_404(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.post("/api/rag/collections/00000000-0000-0000-0000-000000000000/activate")

    assert response.status_code == 404


async def test_excluir_collection_ativa_retorna_409_sem_tocar_qdrant(db_session, active_collection):
    qdrant = _qdrant()
    await qdrant.create_collection(
        name=active_collection.name,
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))

    response = client.delete(f"/api/rag/collections/{active_collection.id}")

    assert response.status_code == 409
    assert await qdrant.collection_exists(active_collection.name) is True


async def test_excluir_collection_inativa_remove_em_cascata(db_session, active_collection):
    from app.rag.collections_registry import create_collection
    from app.rag.registry import create_document

    inativa = await create_collection(
        db_session,
        name="para_excluir",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=inativa.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    qdrant = _qdrant()
    await qdrant.create_collection(
        name="para_excluir",
        vector_dimension=384,
        distance_metric="cosine",
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
        **_DEFAULT_HNSW,
    )
    client = TestClient(_build_app(qdrant, db_session))

    response = client.delete(f"/api/rag/collections/{inativa.id}")

    assert response.status_code == 204
    assert await qdrant.collection_exists("para_excluir") is False
    body = client.get("/api/rag/collections").json()
    assert [c["id"] for c in body] == [str(active_collection.id)]


def test_excluir_collection_inexistente_retorna_404(db_session):
    client = TestClient(_build_app(_qdrant(), db_session))

    response = client.delete("/api/rag/collections/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
