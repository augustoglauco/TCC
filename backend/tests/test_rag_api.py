from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import router as rag_router
from app.api.rag_dependencies import (
    get_db_session,
    get_embedder_registry,
    get_qdrant_client,
    get_uploads_dir,
)
from app.rag.embedders_registry import EmbedderRegistry
from app.router.rag_client import RAGConnectionError
from tests.conftest import _CommitFailingSession, _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


def _build_app(rag_client, db_session, uploads_dir) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_qdrant_client] = lambda: rag_client
    app.dependency_overrides[get_embedder_registry] = lambda: EmbedderRegistry()
    app.dependency_overrides[get_uploads_dir] = lambda: uploads_dir
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_upload_documento_txt_ingere_e_retorna_numero_de_chunks(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"Conteudo de exemplo sobre o catalogo.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"filename": "catalogo.txt", "domain": "vendas", "chunks": 1}
    collection_name, _chunks, source, domain, _document_id = fake.upserts[0]
    assert collection_name == active_collection.name
    assert (source, domain) == ("catalogo.txt", "vendas")


def test_upload_com_collection_id_explicito_usa_essa_collection(
    db_session, active_collection, tmp_path
):
    import asyncio

    from app.rag.collections_registry import create_collection

    outra = asyncio.run(
        create_collection(
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
    )
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas", "collection_id": str(outra.id)},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 200
    collection_name, *_ = fake.upserts[0]
    assert collection_name == "outra"


def test_upload_com_collection_id_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas", "collection_id": "00000000-0000-0000-0000-000000000000"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 404


def test_upload_documento_pdf_ingere(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={
            "file": ("manual.pdf", _build_minimal_pdf("Texto do manual em PDF"), "application/pdf")
        },
    )

    assert response.status_code == 200
    assert response.json()["chunks"] == 1


def test_upload_formato_nao_suportado_retorna_400(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("planilha.csv", b"nao,suportado", "text/csv")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_domain_invalido_retorna_422(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "agendamento"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_com_qdrant_indisponivel_retorna_503(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient(error=RAGConnectionError("qdrant fora do ar"))
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_txt_com_encoding_invalido_retorna_400_em_vez_de_500(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    conteudo_invalido = "áéíóú".encode("latin-1")

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", conteudo_invalido, "text/plain")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_pdf_corrompido_retorna_400_em_vez_de_500(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", b"isto nao e um pdf valido", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_listar_documentos_vazio_retorna_lista_vazia(db_session, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    assert response.json() == []


def test_listar_documentos_apos_upload_retorna_o_documento_com_a_collection(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["filename"] == "catalogo.txt"
    assert body[0]["domain"] == "vendas"
    assert body[0]["origin"] == "upload"
    assert body[0]["chunk_count"] == 1
    assert body[0]["collection_id"] == str(active_collection.id)
    assert body[0]["collection_name"] == active_collection.name


def test_excluir_documento_existente_remove_do_registro_do_qdrant_e_do_disco(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    documento = client.get("/api/rag/documents").json()[0]
    document_id = documento["id"]

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 204
    assert client.get("/api/rag/documents").json() == []
    assert fake.deleted == [(active_collection.name, document_id)]
    arquivos_restantes = list((tmp_path).rglob("*catalogo.txt"))
    assert arquivos_restantes == []


def test_excluir_documento_inexistente_retorna_404_sem_chamar_qdrant(db_session, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    document_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 404
    assert fake.deleted == []


def test_reingest_documento_cria_novo_registro_na_collection_destino(
    db_session, active_collection, tmp_path
):
    import asyncio

    from app.rag.collections_registry import create_collection

    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]
    destino = asyncio.run(
        create_collection(
            db_session,
            name="destino",
            embedding_model="fake-embedding-model",
            vector_dimension=384,
            distance_metric="cosine",
            chunk_size=400,
            chunk_overlap=50,
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
    )

    response = client.post(
        f"/api/rag/documents/{document_id}/reingest", json={"target_collection_id": str(destino.id)}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["collection_id"] == str(destino.id)
    assert body["origin"] == "reingest"
    assert UUID(body["id"]) != UUID(document_id)


def test_reingest_documento_inexistente_retorna_404(db_session, active_collection, tmp_path):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents/00000000-0000-0000-0000-000000000000/reingest",
        json={"target_collection_id": str(active_collection.id)},
    )

    assert response.status_code == 404


def test_reingest_para_a_propria_collection_de_origem_retorna_409(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]

    response = client.post(
        f"/api/rag/documents/{document_id}/reingest",
        json={"target_collection_id": str(active_collection.id)},
    )

    assert response.status_code == 409


def test_reingest_para_collection_destino_inexistente_retorna_404(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]

    response = client.post(
        f"/api/rag/documents/{document_id}/reingest",
        json={"target_collection_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404


async def test_reingest_com_erro_no_postgres_retorna_503(db_session, active_collection, tmp_path):
    """`reingest_document_endpoint` também precisa tratar `SQLAlchemyError`
    como os outros três endpoints deste arquivo (achado #2 da revisão
    final) — antes só capturava `RAGConnectionError`."""
    from app.rag.collections_registry import create_collection

    fake = _FakeQdrantRAGClient()
    setup_client = TestClient(_build_app(fake, db_session, tmp_path))
    setup_client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = setup_client.get("/api/rag/documents").json()[0]["id"]
    destino = await create_collection(
        db_session,
        name="destino",
        embedding_model="fake-embedding-model",
        vector_dimension=384,
        distance_metric="cosine",
        chunk_size=400,
        chunk_overlap=50,
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
    failing_client = TestClient(_build_app(fake, _CommitFailingSession(db_session), tmp_path))

    response = failing_client.post(
        f"/api/rag/documents/{document_id}/reingest", json={"target_collection_id": str(destino.id)}
    )

    assert response.status_code == 503
