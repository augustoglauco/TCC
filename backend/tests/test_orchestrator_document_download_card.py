"""Testes do card `CardDocumentoDownload` (Task 2 do plano de download de
documentos no chat, `.superpowers/sdd/2026-10-04-download-documentos-rag-chat/`).

Cobre o schema Pydantic isolado e `_construir_card_documento_download`
(orchestrator) — o card só deve ser emitido quando o melhor chunk do RAG bate
com confiança alta E o documento correspondente pertence a uma collection
`purpose="chat"` (mesma collection cujo endpoint de download, Task 1, é
público sem token — ver docs/ARCHITECTURE.md §7).
"""

import uuid
from datetime import UTC, datetime

from app.db.models import RagCollection, RagDocument
from app.models.chat import CardDocumentoDownload
from app.router.orchestrator import _construir_card_documento_download
from app.router.rag_client import Document


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


class _MockSessionMaker:
    """Mesmo dublê usado em `test_chat_chart_card.py`: embrulha uma única
    `AsyncSession` já aberta (fixture `db_session`) para parecer um
    `async_sessionmaker` do ponto de vista de `async with db_sessionmaker()`."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self._session


def test_card_documento_download_schema():
    card = CardDocumentoDownload(
        documento_id="123e4567-e89b-12d3-a456-426614174000",
        filename="Manual_GD30.pdf",
        domain="suporte",
        score=0.88,
        download_url="/api/rag/documents/123e4567-e89b-12d3-a456-426614174000/download",
        file_size_bytes=2450000,
    )
    assert card.tipo == "documento_download"
    assert card.documento_id == "123e4567-e89b-12d3-a456-426614174000"
    assert card.filename == "Manual_GD30.pdf"
    assert card.domain == "suporte"
    assert card.score == 0.88
    assert card.file_size_bytes == 2450000


async def test_card_emitido_quando_score_alto_e_collection_purpose_chat(db_session, tmp_path):
    col = _make_collection("chat")
    arquivo = tmp_path / "Manual_GD30.pdf"
    conteudo = b"%PDF-1.4 conteudo de teste do manual"
    arquivo.write_bytes(conteudo)
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    documentos = [Document(content="trecho relevante", source="Manual_GD30.pdf", score=0.88)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is not None
    assert card.tipo == "documento_download"
    assert card.documento_id == str(doc.id)
    assert card.filename == "Manual_GD30.pdf"
    assert card.domain == "suporte"
    assert card.score == 0.88
    assert card.download_url == f"/api/rag/documents/{doc.id}/download"
    assert card.file_size_bytes == len(conteudo)


async def test_card_nao_emitido_quando_score_abaixo_do_limiar(db_session, tmp_path):
    col = _make_collection("chat")
    arquivo = tmp_path / "Manual_GD30.pdf"
    arquivo.write_bytes(b"conteudo")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    documentos = [Document(content="trecho", source="Manual_GD30.pdf", score=0.40)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is None


async def test_card_nao_emitido_quando_collection_purpose_nao_e_chat(db_session, tmp_path):
    col = _make_collection("admin")
    arquivo = tmp_path / "Manual_Interno.pdf"
    arquivo.write_bytes(b"conteudo interno")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="Manual_Interno.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    documentos = [Document(content="trecho", source="Manual_Interno.pdf", score=0.90)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is None


async def test_card_nao_emitido_quando_nenhum_documento_corresponde(db_session):
    documentos = [Document(content="trecho", source="Arquivo_Que_Nao_Existe.pdf", score=0.90)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is None


async def test_card_nao_emitido_quando_arquivo_nao_existe_em_disco(db_session, tmp_path):
    col = _make_collection("chat")
    doc = RagDocument(
        id=uuid.uuid4(),
        collection_id=col.id,
        filename="Manual_Perdido.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(tmp_path / "Manual_Perdido.pdf"),
        origin="upload",
    )
    db_session.add_all([col, doc])
    await db_session.commit()

    documentos = [Document(content="trecho", source="Manual_Perdido.pdf", score=0.90)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is None


async def test_card_nao_emitido_quando_db_sessionmaker_e_none():
    documentos = [Document(content="trecho", source="Manual_GD30.pdf", score=0.90)]

    card = await _construir_card_documento_download(None, documentos, "suporte", 0.65)

    assert card is None


async def test_card_nao_emitido_quando_lista_de_documentos_vazia(db_session):
    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), [], "suporte", 0.65
    )

    assert card is None


async def test_card_resolve_documento_correto_quando_filename_duplicado_entre_collections(
    db_session, tmp_path
):
    """Achado importante 1 da revisão final: `reingest_document`
    (app/rag/ingest.py) cria deliberadamente uma NOVA linha `RagDocument`
    com o mesmo filename+domain numa collection diferente ao reingerir —
    duplicatas entre collections são estado normal, não corner case. A
    query do card precisa resolver sempre a linha de uma collection
    `purpose="chat"`, nunca uma de `purpose="admin"` (ou outro), mesmo
    quando as duas casam por filename+domain."""
    col_admin = _make_collection("admin")
    col_chat = _make_collection("chat")
    arquivo = tmp_path / "Manual_GD30.pdf"
    conteudo = b"conteudo do manual reingerido"
    arquivo.write_bytes(conteudo)

    doc_admin = RagDocument(
        id=uuid.uuid4(),
        collection_id=col_admin.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(tmp_path / "Manual_GD30_admin_nao_deveria_ser_escolhido.pdf"),
        origin="upload",
    )
    doc_chat = RagDocument(
        id=uuid.uuid4(),
        collection_id=col_chat.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo),
        origin="upload",
    )
    db_session.add_all([col_admin, col_chat, doc_admin, doc_chat])
    await db_session.commit()

    documentos = [Document(content="trecho relevante", source="Manual_GD30.pdf", score=0.88)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is not None
    assert card.documento_id == str(doc_chat.id)
    assert card.file_size_bytes == len(conteudo)


async def test_card_resolve_documento_mais_recente_quando_duas_collections_purpose_chat(
    db_session, tmp_path
):
    """Desempate determinístico: se mais de uma linha `purpose="chat"`
    casar por filename+domain (ex.: duas reingestões sucessivas em
    collections `chat` diferentes), o card deve apontar para a mais
    recente (`created_at` maior), não para uma escolhida arbitrariamente
    pelo banco."""
    col_chat_antiga = _make_collection("chat")
    col_chat_nova = _make_collection("chat")

    arquivo_antigo = tmp_path / "antigo.pdf"
    arquivo_antigo.write_bytes(b"versao antiga")
    arquivo_novo = tmp_path / "novo.pdf"
    conteudo_novo = b"versao nova reingerida"
    arquivo_novo.write_bytes(conteudo_novo)

    doc_antigo = RagDocument(
        id=uuid.uuid4(),
        collection_id=col_chat_antiga.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo_antigo),
        origin="upload",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    doc_novo = RagDocument(
        id=uuid.uuid4(),
        collection_id=col_chat_nova.id,
        filename="Manual_GD30.pdf",
        domain="suporte",
        chunk_count=5,
        storage_path=str(arquivo_novo),
        origin="upload",
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db_session.add_all([col_chat_antiga, col_chat_nova, doc_antigo, doc_novo])
    await db_session.commit()

    documentos = [Document(content="trecho relevante", source="Manual_GD30.pdf", score=0.88)]

    card = await _construir_card_documento_download(
        _MockSessionMaker(db_session), documentos, "suporte", 0.65
    )

    assert card is not None
    assert card.documento_id == str(doc_novo.id)
    assert card.file_size_bytes == len(conteudo_novo)
