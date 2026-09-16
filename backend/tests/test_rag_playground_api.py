import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.api.rag_playground import router as rag_playground_router
from app.rag.embedders_registry import EmbedderRegistry
from app.router.rag_client import Document, RAGConnectionError


class _FakeQdrantSearch:
    def __init__(self, resultado=None, error: Exception | None = None) -> None:
        self._resultado = resultado or []
        self._error = error
        self.chamadas: list[str] = []

    async def search(
        self, collection_name, embedder, query, domain, top_k=None, score_threshold=None
    ):
        self.chamadas.append(collection_name)
        if self._error is not None:
            raise self._error
        return self._resultado


def _build_app(qdrant, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_playground_router)
    app.dependency_overrides[get_qdrant_client] = lambda: qdrant
    app.dependency_overrides[get_embedder_registry] = lambda: EmbedderRegistry()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


async def test_playground_busca_em_uma_collection_e_retorna_resultado_com_latencia(
    db_session, active_collection
):
    fake = _FakeQdrantSearch(resultado=[Document(content="conteúdo", source="a.txt", score=0.9)])
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/playground/search",
        json={
            "query": "pergunta de teste",
            "domain": "vendas",
            "collection_ids": [str(active_collection.id)],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["collection_name"] == active_collection.name
    assert item["latency_ms"] >= 0
    assert item["results"] == [{"content": "conteúdo", "source": "a.txt", "score": 0.9}]
    assert item["error"] is None


async def test_playground_com_collection_inexistente_retorna_item_com_erro(db_session):
    fake = _FakeQdrantSearch()
    client = TestClient(_build_app(fake, db_session))
    id_inexistente = str(uuid.uuid4())

    response = client.post(
        "/api/rag/playground/search",
        json={"query": "pergunta", "domain": "vendas", "collection_ids": [id_inexistente]},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["collection_id"] == id_inexistente
    assert item["error"] is not None
    assert item["results"] == []


async def test_playground_erro_de_conexao_em_uma_collection_nao_derruba_as_outras(
    db_session, active_collection
):
    from app.rag.collections_registry import create_collection

    outra = await create_collection(
        db_session,
        name="outra",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=800,
        chunk_overlap=100,
        hnsw_m=16,
        hnsw_ef_construct=100,
        hnsw_full_scan_threshold=10000,
        hnsw_max_indexing_threads=0,
        hnsw_on_disk=False,
        hnsw_payload_m=None,
        quantization_type="none",
        quantization_config={},
        payload_indexes=[],
    )

    class _FlakyQdrant:
        async def search(
            self, collection_name, embedder, query, domain, top_k=None, score_threshold=None
        ):
            if collection_name == active_collection.name:
                raise RAGConnectionError("fora do ar")
            return [Document(content="ok", source="b.txt", score=0.5)]

    client = TestClient(_build_app(_FlakyQdrant(), db_session))

    response = client.post(
        "/api/rag/playground/search",
        json={
            "query": "pergunta",
            "domain": "vendas",
            "collection_ids": [str(active_collection.id), str(outra.id)],
        },
    )

    assert response.status_code == 200
    items = {item["collection_id"]: item for item in response.json()["items"]}
    assert items[str(active_collection.id)]["error"] is not None
    assert items[str(outra.id)]["results"][0]["source"] == "b.txt"


async def test_playground_sem_collection_ids_retorna_422(db_session):
    fake = _FakeQdrantSearch()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/playground/search",
        json={"query": "pergunta", "domain": "vendas", "collection_ids": []},
    )

    assert response.status_code == 422
