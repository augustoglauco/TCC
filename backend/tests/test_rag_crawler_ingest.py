from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_ingest import ingest_or_queue, replace_previous_ingestion
from app.rag.crawler_pending import list_pending_pages
from app.rag.registry import list_documents
from tests.conftest import _FakeQdrantRAGClient


async def test_replace_previous_ingestion_noop_quando_nunca_ingerido(db_session, active_collection):
    fake = _FakeQdrantRAGClient()

    await replace_previous_ingestion(db_session, fake, active_collection, "https://exemplo.com/a")

    assert fake.deleted == []


async def test_ingest_or_queue_confidence_alta_ingere(db_session, active_collection, tmp_path):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.9)

    outcome = await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/produtos",
        "conteúdo da página de produtos",
        classification,
        confidence_threshold=0.7,
    )

    assert outcome == "ingested"
    assert len(fake.upserts) == 1
    _collection_name, _chunks, source, domain, _document_id = fake.upserts[0]
    assert (source, domain) == ("https://exemplo.com/produtos", "vendas")
    assert await list_pending_pages(db_session) == []


async def test_ingest_or_queue_confidence_baixa_enfileira(db_session, active_collection, tmp_path):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.3)

    outcome = await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/ambiguo",
        "conteúdo ambíguo",
        classification,
        confidence_threshold=0.7,
    )

    assert outcome == "queued"
    assert fake.upserts == []
    pendentes = await list_pending_pages(db_session)
    assert len(pendentes) == 1
    assert pendentes[0].url == "https://exemplo.com/ambiguo"


async def test_ingest_or_queue_recrawl_url_ja_ingerida_substitui(
    db_session, active_collection, tmp_path
):
    from app.rag.embedders_registry import EmbedderRegistry

    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    classification = PageClassification(domain="vendas", confidence=0.9)

    await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/produtos",
        "versão 1",
        classification,
        confidence_threshold=0.7,
    )
    primeiro_document_id = fake.upserts[0][4]

    await ingest_or_queue(
        db_session,
        fake,
        active_collection,
        embedder,
        tmp_path,
        "https://exemplo.com/produtos",
        "versão 2",
        classification,
        confidence_threshold=0.7,
    )

    assert fake.deleted == [(active_collection.name, primeiro_document_id)]
    documentos = await list_documents(db_session)
    assert len(documentos) == 1
    assert documentos[0].filename == "https://exemplo.com/produtos"
