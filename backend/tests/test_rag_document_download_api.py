"""Testes do endpoint `GET /api/rag/documents/{id}/download` (Task 1 do
plano de cards de download no chat,
`.superpowers/sdd/2026-10-04-download-documentos-rag-chat/`).

Decisão de 2026-10-05 (`docs/ARCHITECTURE.md` §7): download é público (sem
token) quando a collection de origem tem `purpose="chat"` e exige o mesmo
`require_admin` dos demais endpoints de `/api/rag/documents/*` para
qualquer outro `purpose`. Mirror de `test_obter_conteudo_do_documento_*`
em `test_rag_api.py`, mas usando `/download` (sem exigir token para
`purpose="chat"`) em vez de `/content` (sempre exige `require_admin`).
"""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag import router as rag_router
from app.api.rag_dependencies import get_db_session, get_uploads_dir
from app.db.models import RagCollection, RagDocument


def _build_app(db_session, uploads_dir) -> FastAPI:
    app = FastAPI()
    app.include_router(rag_router)
    app.dependency_overrides[get_uploads_dir] = lambda: uploads_dir
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def _make_collection(purpose: str) -> RagCollection:
    return RagCollection(
        id=uuid.uuid4(),
        name=f"col_{purpose}_{uuid.uuid4().hex[:8]}",
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
        is_active=False,
        purpose=purpose,
    )


async def test_download_documento_de_collection_chat_nao_exige_token(db_session, tmp_path):
    """Documento de uma collection `purpose="chat"` (o padrão usado pelo
    widget público) pode ser baixado por visitante anônimo, sem nenhum
    header/param de autenticação."""
    col = _make_collection("chat")
    test_file = tmp_path / "manual_teste.pdf"
    test_file.write_bytes(b"%PDF-1.4 mock content")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="manual_teste.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(test_file),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    client = TestClient(_build_app(db_session, tmp_path))
    response = client.get(f"/api/rag/documents/{doc.id}/download")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="manual_teste.pdf"'
    assert response.content == b"%PDF-1.4 mock content"


async def test_download_documento_de_collection_admin_exige_token_valido(
    db_session, tmp_path, admin_headers
):
    """Documento de uma collection `purpose="admin"` continua exigindo o
    mesmo `require_admin` dos outros endpoints de `/api/rag/documents/*`:
    403 sem token, 200 com um token admin válido."""
    col = _make_collection("admin")
    test_file = tmp_path / "manual_interno.pdf"
    test_file.write_bytes(b"%PDF-1.4 conteudo interno")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="manual_interno.pdf",
        domain="suporte",
        chunk_count=3,
        storage_path=str(test_file),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    client = TestClient(_build_app(db_session, tmp_path))

    sem_token = client.get(f"/api/rag/documents/{doc.id}/download")
    assert sem_token.status_code == 403

    com_token = client.get(f"/api/rag/documents/{doc.id}/download", headers=admin_headers)
    assert com_token.status_code == 200
    assert com_token.content == b"%PDF-1.4 conteudo interno"


async def test_download_documento_inexistente_retorna_404(db_session, tmp_path):
    client = TestClient(_build_app(db_session, tmp_path))

    response = client.get(
        f"/api/rag/documents/{uuid.uuid4()}/download",
    )

    assert response.status_code == 404


async def test_download_documento_sem_arquivo_em_disco_retorna_404_limpo(db_session, tmp_path):
    """`storage_path` aponta para um arquivo que não existe mais em disco —
    deve dar 404 (igual ao `/content`), nunca 500."""
    col = _make_collection("chat")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="arquivo_perdido.pdf",
        domain="suporte",
        chunk_count=1,
        storage_path=str(tmp_path / "arquivo_perdido.pdf"),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    client = TestClient(_build_app(db_session, tmp_path))
    response = client.get(f"/api/rag/documents/{doc.id}/download")

    assert response.status_code == 404
