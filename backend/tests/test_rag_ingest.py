from pathlib import Path

from app.rag.chunking import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE
from app.rag.ingest import ingest_bytes, ingest_directory, ingest_file
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


async def test_ingest_file_le_txt_faz_chunking_e_grava_com_domain_informado(
    tmp_path: Path, db_session
):
    arquivo = tmp_path / "catalogo.txt"
    arquivo.write_text("Conteúdo de exemplo sobre o catálogo de produtos.", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(
        client, arquivo, domain="vendas", session=db_session, origin="upload"
    )

    assert documento.filename == "catalogo.txt"
    assert documento.domain == "vendas"
    assert documento.chunk_count == 1
    assert documento.embedding_model == client.embedding_model_name
    assert documento.chunk_size == DEFAULT_CHUNK_SIZE
    assert documento.chunk_overlap == DEFAULT_CHUNK_OVERLAP
    assert documento.origin == "upload"
    chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo de produtos" in chunks[0]


async def test_ingest_file_extrai_texto_de_pdf(tmp_path: Path, db_session):
    arquivo = tmp_path / "manual.pdf"
    arquivo.write_bytes(_build_minimal_pdf("Texto do manual em PDF"))
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(
        client, arquivo, domain="suporte", session=db_session, origin="upload"
    )

    assert documento.chunk_count == 1
    chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_ingest_directory_infere_domain_do_subdiretorio_e_ignora_extensao_nao_suportada(
    tmp_path: Path,
    db_session,
):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "catalogo.txt").write_text("catálogo de vendas", encoding="utf-8")
    (tmp_path / "suporte").mkdir()
    (tmp_path / "suporte" / "manual.txt").write_text("manual de suporte técnico", encoding="utf-8")
    (tmp_path / "suporte" / "planilha.csv").write_text("nao,deveria,entrar", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(client, tmp_path, session=db_session)

    assert len(documentos) == 2
    domains_ingeridos = {documento.domain for documento in documentos}
    assert domains_ingeridos == {"vendas", "suporte"}
    assert all(documento.origin == "batch_script" for documento in documentos)


async def test_ingest_directory_sem_arquivos_suportados_retorna_lista_vazia(
    tmp_path: Path, db_session
):
    (tmp_path / "vendas").mkdir()
    (tmp_path / "vendas" / "planilha.csv").write_text("nao,suportado", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(client, tmp_path, session=db_session)

    assert documentos == []
    assert client.upserts == []


async def test_ingest_bytes_le_txt_faz_chunking_e_grava_com_domain_informado(db_session):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        "catalogo.txt",
        "Conteúdo de exemplo sobre o catálogo.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo" in chunks[0]


async def test_ingest_bytes_extrai_texto_de_pdf(db_session):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        "manual.pdf",
        _build_minimal_pdf("Texto do manual em PDF"),
        domain="suporte",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]
