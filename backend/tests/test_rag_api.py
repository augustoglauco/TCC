from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import get_rag_client
from app.api.rag import router as rag_router
from app.router.rag_client import RAGConnectionError
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


def _build_app(rag_client) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_rag_client] = lambda: rag_client
    return app


def test_upload_documento_txt_ingere_e_retorna_numero_de_chunks():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"Conteudo de exemplo sobre o catalogo.", "text/plain")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"filename": "catalogo.txt", "domain": "vendas", "chunks": 1}
    assert fake.upserts[0][1:3] == ("catalogo.txt", "vendas")


def test_upload_documento_pdf_ingere():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

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


def test_upload_formato_nao_suportado_retorna_400():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("planilha.csv", b"nao,suportado", "text/csv")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_domain_invalido_retorna_422():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "agendamento"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 422


def test_upload_com_qdrant_indisponivel_retorna_503():
    fake = _FakeQdrantRAGClient(error=RAGConnectionError("qdrant fora do ar"))
    client = TestClient(_build_app(fake))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", b"conteudo", "text/plain")},
    )

    assert response.status_code == 503


def test_upload_txt_com_encoding_invalido_retorna_400_em_vez_de_500():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

    # "áéíóú" em Windows-1252 (Latin-1), não decodificável como UTF-8.
    conteudo_invalido = "áéíóú".encode("latin-1")

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={"file": ("catalogo.txt", conteudo_invalido, "text/plain")},
    )

    assert response.status_code == 400
    assert fake.upserts == []


def test_upload_pdf_corrompido_retorna_400_em_vez_de_500():
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "suporte"},
        files={"file": ("manual.pdf", b"isto nao e um pdf valido", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake.upserts == []
