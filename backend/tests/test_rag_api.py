from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import get_db_session, get_rag_client
from app.api.rag import router as rag_router
from app.router.rag_client import RAGConnectionError
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


def _build_app(rag_client, db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_rag_client] = lambda: rag_client
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_upload_documento_txt_ingere_e_retorna_numero_de_chunks(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"Conteudo de exemplo sobre o catalogo.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"filename": "catalogo.txt", "domain": "vendas", "chunks": 1}
    assert fake.upserts[0][1:3] == ("catalogo.txt", "vendas")


def test_upload_documento_pdf_ingere(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={
            "file": (
                "manual.pdf",
                _build_minimal_pdf("Texto do manual em PDF"),
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["chunks"] == 1


def test_upload_formato_nao_suportado_retorna_400(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("planilha.csv", b"nao,suportado", "text/csv")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_domain_invalido_retorna_422(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "agendamento"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_com_qdrant_indisponivel_retorna_503(db_session):
    fake = _FakeQdrantRAGClient(error=RAGConnectionError("qdrant fora do ar"))
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_txt_com_encoding_invalido_retorna_400_em_vez_de_500(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    conteudo_invalido = "áéíóú".encode("latin-1")

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", conteudo_invalido, "text/plain")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_pdf_corrompido_retorna_400_em_vez_de_500(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", b"isto nao e um pdf valido", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_listar_documentos_vazio_retorna_lista_vazia(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))

    response = client.get("/api/rag/documents")

    assert response.status_code == 200
    assert response.json() == []


def test_listar_documentos_apos_upload_retorna_o_documento(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))
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


def test_excluir_documento_existente_remove_do_registro_e_do_qdrant(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))
    client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo de exemplo", "text/plain")},
    )
    document_id = client.get("/api/rag/documents").json()[0]["id"]

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 204
    assert client.get("/api/rag/documents").json() == []
    assert fake.deleted_document_ids == [document_id]


def test_excluir_documento_inexistente_retorna_404(db_session):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session))
    document_id = "00000000-0000-0000-0000-000000000000"

    response = client.delete(f"/api/rag/documents/{document_id}")

    assert response.status_code == 404
    assert fake.deleted_document_ids == [document_id]
