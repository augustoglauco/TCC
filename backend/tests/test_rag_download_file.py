"""Arquivo de download separado do arquivo ingerido (`rag_documents.download_path`).

O `.md` tratado é o que o RAG indexa; o PDF original do fornecedor é o que o
cliente baixa no card do chat. Sem `download_file`, tudo se comporta como antes
(o download devolve o arquivo ingerido). Decisão de 2026-10-31 em
`docs/ARCHITECTURE.md`.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient

from app.db.models import RagDocument
from app.rag.collections_registry import create_collection
from app.router.orchestrator import _construir_card_documento_download
from app.router.rag_client import Document
from tests.conftest import _FakeQdrantRAGClient
from tests.test_orchestrator_document_download_card import _make_collection, _MockSessionMaker
from tests.test_rag_api import _build_app

_PDF = b"%PDF-1.4 manual original do fornecedor"
_MD = b"# idaccess\n\nTexto tratado do manual."


def _subir(client, admin_headers, *, com_download: bool = True):
    files = {"file": ("idaccess.md", _MD, "text/markdown")}
    if com_download:
        files["download_file"] = ("idaccess.pdf", _PDF, "application/pdf")
    return client.post(
        "/api/rag/documents", data={"domain": "vendas"}, files=files, headers=admin_headers
    )


def test_upload_com_download_file_guarda_os_dois_arquivos_e_lista_o_nome(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))

    response = _subir(client, admin_headers)

    assert response.status_code == 200
    documento = client.get("/api/rag/documents", headers=admin_headers).json()[0]
    assert documento["filename"] == "idaccess.md"
    assert documento["download_filename"] == "idaccess.pdf"
    assert len(list(tmp_path.glob("*_idaccess.md"))) == 1
    assert len(list(tmp_path.glob("*_download_idaccess.pdf"))) == 1


def test_upload_sem_download_file_nao_tem_download_filename(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))

    _subir(client, admin_headers, com_download=False)

    documento = client.get("/api/rag/documents", headers=admin_headers).json()[0]
    assert documento["download_filename"] is None
    assert list(tmp_path.glob("*_download_*")) == []


def test_upload_com_download_file_de_formato_invalido_retorna_400_sem_ingerir(
    db_session, active_collection, tmp_path, admin_headers
):
    fake = _FakeQdrantRAGClient()
    client = TestClient(_build_app(fake, db_session, tmp_path))

    response = client.post(
        "/api/rag/documents",
        data={"domain": "vendas"},
        files={
            "file": ("idaccess.md", _MD, "text/markdown"),
            "download_file": ("instalador.exe", b"MZ", "application/octet-stream"),
        },
        headers=admin_headers,
    )

    assert response.status_code == 400
    assert fake.upserts == []
    assert client.get("/api/rag/documents", headers=admin_headers).json() == []


def test_download_devolve_o_pdf_associado_com_o_nome_do_pdf(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))
    _subir(client, admin_headers)
    document_id = client.get("/api/rag/documents", headers=admin_headers).json()[0]["id"]

    response = client.get(f"/api/rag/documents/{document_id}/download")

    assert response.status_code == 200
    assert response.content == _PDF
    assert response.headers["content-disposition"] == 'attachment; filename="idaccess.pdf"'


def test_download_sem_pdf_associado_devolve_o_arquivo_ingerido(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))
    _subir(client, admin_headers, com_download=False)
    document_id = client.get("/api/rag/documents", headers=admin_headers).json()[0]["id"]

    response = client.get(f"/api/rag/documents/{document_id}/download")

    assert response.content == _MD
    assert response.headers["content-disposition"] == 'attachment; filename="idaccess.md"'


def test_content_do_admin_continua_mostrando_o_arquivo_ingerido(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))
    _subir(client, admin_headers)
    document_id = client.get("/api/rag/documents", headers=admin_headers).json()[0]["id"]

    response = client.get(f"/api/rag/documents/{document_id}/content", headers=admin_headers)

    assert response.content == _MD


def test_excluir_documento_remove_tambem_o_arquivo_de_download(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))
    _subir(client, admin_headers)
    document_id = client.get("/api/rag/documents", headers=admin_headers).json()[0]["id"]

    response = client.delete(f"/api/rag/documents/{document_id}", headers=admin_headers)

    assert response.status_code == 204
    assert list(tmp_path.glob("*idaccess*")) == []


def test_reingest_preserva_o_arquivo_de_download(
    db_session, active_collection, tmp_path, admin_headers
):
    client = TestClient(_build_app(_FakeQdrantRAGClient(), db_session, tmp_path))
    _subir(client, admin_headers)
    document_id = client.get("/api/rag/documents", headers=admin_headers).json()[0]["id"]
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
        f"/api/rag/documents/{document_id}/reingest",
        json={"target_collection_id": str(destino.id)},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["download_filename"] == "idaccess.pdf"


async def test_card_do_chat_usa_nome_e_tamanho_do_pdf(db_session, tmp_path):
    col = _make_collection("chat")
    ingerido = tmp_path / "idaccess.md"
    ingerido.write_bytes(_MD)
    pdf = tmp_path / "abc_download_idaccess.pdf"
    pdf.write_bytes(_PDF)
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="idaccess.md",
        domain="suporte",
        chunk_count=2,
        storage_path=str(ingerido),
        download_path=str(pdf),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()
    documentos = [Document(content="trecho", source="idaccess.md", score=0.8)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is not None
    assert card.filename == "idaccess.pdf"
    assert card.file_size_bytes == len(_PDF)
    assert card.download_url == f"/api/rag/documents/{doc.id}/download"


async def test_card_do_chat_some_quando_o_pdf_associado_nao_esta_em_disco(db_session, tmp_path):
    col = _make_collection("chat")
    ingerido = tmp_path / "idaccess.md"
    ingerido.write_bytes(_MD)
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="idaccess.md",
        domain="suporte",
        chunk_count=2,
        storage_path=str(ingerido),
        download_path=str(tmp_path / "abc_download_sumiu.pdf"),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()
    documentos = [Document(content="trecho", source="idaccess.md", score=0.8)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is None
