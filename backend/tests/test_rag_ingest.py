from pathlib import Path

import pytest

from app.rag.ingest import ingest_bytes, ingest_directory, ingest_file, reingest_document
from tests.conftest import _FakeQdrantRAGClient
from tests.test_rag_pdf_extract import _build_minimal_pdf


async def test_ingest_file_le_txt_faz_chunking_e_grava_com_domain_informado(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    arquivo = tmp_path / "catalogo.txt"
    arquivo.write_text("Conteúdo de exemplo sobre o catálogo de produtos.", encoding="utf-8")
    client = _FakeQdrantRAGClient()
    uploads_dir = tmp_path / "uploads"

    documento = await ingest_file(
        client,
        text_embedder,
        active_collection,
        uploads_dir,
        arquivo,
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    assert documento.filename == "catalogo.txt"
    assert documento.domain == "vendas"
    assert documento.chunk_count == 1
    assert documento.collection_id == active_collection.id
    assert documento.storage_path is not None
    assert Path(documento.storage_path).read_bytes() == arquivo.read_bytes()
    assert documento.origin == "upload"
    collection_name, chunks, source, domain, document_id = client.upserts[0]
    assert collection_name == active_collection.name
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo de produtos" in chunks[0]


async def test_ingest_file_extrai_texto_de_pdf(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    arquivo = tmp_path / "manual.pdf"
    arquivo.write_bytes(_build_minimal_pdf("Texto do manual em PDF"))
    client = _FakeQdrantRAGClient()

    documento = await ingest_file(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        arquivo,
        domain="suporte",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_ingest_directory_infere_domain_do_subdiretorio_e_ignora_extensao_nao_suportada(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    origem = tmp_path / "origem"
    (origem / "vendas").mkdir(parents=True)
    (origem / "vendas" / "catalogo.txt").write_text("catálogo de vendas", encoding="utf-8")
    (origem / "suporte").mkdir()
    (origem / "suporte" / "manual.txt").write_text("manual de suporte técnico", encoding="utf-8")
    (origem / "suporte" / "planilha.csv").write_text("nao,deveria,entrar", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        origem,
        session=db_session,
    )

    assert len(documentos) == 2
    domains_ingeridos = {documento.domain for documento in documentos}
    assert domains_ingeridos == {"vendas", "suporte"}
    assert all(documento.origin == "batch_script" for documento in documentos)


async def test_ingest_directory_sem_arquivos_suportados_retorna_lista_vazia(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    origem = tmp_path / "origem"
    (origem / "vendas").mkdir(parents=True)
    (origem / "vendas" / "planilha.csv").write_text("nao,suportado", encoding="utf-8")
    client = _FakeQdrantRAGClient()

    documentos = await ingest_directory(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        origem,
        session=db_session,
    )

    assert documentos == []
    assert client.upserts == []


async def test_ingest_bytes_le_txt_faz_chunking_e_grava_com_domain_informado(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        "catalogo.txt",
        "Conteúdo de exemplo sobre o catálogo.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, source, domain, document_id = client.upserts[0]
    assert source == "catalogo.txt"
    assert domain == "vendas"
    assert document_id == str(documento.id)
    assert "catálogo" in chunks[0]


async def test_ingest_bytes_recria_collection_no_qdrant_se_nao_existir(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    """Fresh install / collection apagada por fora do app: `ingest_bytes` não
    deve depender de a collection já existir no Qdrant, e sim recriá-la a
    partir do próprio perfil salvo em `active_collection` (ver finding #3 da
    revisão final, self-healing em `app.rag.ingest.ingest_bytes`)."""
    client = _FakeQdrantRAGClient(collections_existentes=set())

    documento = await ingest_bytes(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        "catalogo.txt",
        "Conteúdo de exemplo.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    assert client.created_collections == [active_collection.name]
    assert await client.collection_exists(active_collection.name) is True


async def test_ingest_bytes_sanitiza_filename_com_separador_de_diretorio(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    """`storage_path` não pode herdar componentes de diretório de um
    `filename` malicioso/inesperado — ver finding #5 da revisão final."""
    client = _FakeQdrantRAGClient()
    uploads_dir = tmp_path / "uploads"

    documento = await ingest_bytes(
        client,
        text_embedder,
        active_collection,
        uploads_dir,
        "../evil.txt",
        "Conteúdo qualquer.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )

    storage_path = Path(documento.storage_path)
    assert storage_path.parent == uploads_dir
    assert storage_path.name.endswith("_evil.txt")
    assert storage_path.read_bytes() == "Conteúdo qualquer.".encode()


async def test_ingest_bytes_extrai_texto_de_pdf(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    client = _FakeQdrantRAGClient()

    documento = await ingest_bytes(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        "manual.pdf",
        _build_minimal_pdf("Texto do manual em PDF"),
        domain="suporte",
        session=db_session,
        origin="upload",
    )

    assert documento.chunk_count == 1
    _collection_name, chunks, _source, _domain, _document_id = client.upserts[0]
    assert "Texto do manual em PDF" in chunks[0]


async def test_reingest_document_le_arquivo_salvo_e_grava_na_collection_destino(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    from app.rag.collections_registry import create_collection

    client = _FakeQdrantRAGClient()
    original = await ingest_bytes(
        client,
        text_embedder,
        active_collection,
        tmp_path / "uploads",
        "catalogo.txt",
        "Conteúdo original.".encode(),
        domain="vendas",
        session=db_session,
        origin="upload",
    )
    destino = await create_collection(
        db_session,
        name="destino",
        embedding_model="outro-modelo",
        vector_dimension=768,
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

    reingerido = await reingest_document(
        client, text_embedder, original, destino, session=db_session
    )

    assert reingerido.id != original.id
    assert reingerido.collection_id == destino.id
    assert reingerido.filename == "catalogo.txt"
    assert reingerido.origin == "reingest"
    assert reingerido.storage_path == original.storage_path
    collection_name, _chunks, _source, _domain, _document_id = client.upserts[-1]
    assert collection_name == "destino"


async def test_reingest_document_sem_storage_path_levanta_value_error(
    db_session, active_collection, text_embedder
):
    import uuid

    from app.rag.registry import create_document

    documento_antigo = await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=active_collection.id,
        filename="antigo.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )
    client = _FakeQdrantRAGClient()

    with pytest.raises(ValueError):
        await reingest_document(
            client, text_embedder, documento_antigo, active_collection, session=db_session
        )
