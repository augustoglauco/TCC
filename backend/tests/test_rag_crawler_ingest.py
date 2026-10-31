from app.rag.crawler_classifier import PageClassification
from app.rag.crawler_ingest import queue_page, replace_previous_ingestion
from app.rag.crawler_pending import list_pending_pages
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_bytes
from app.rag.registry import list_documents
from tests.conftest import _FakeQdrantRAGClient


async def test_replace_previous_ingestion_noop_quando_nunca_ingerido(db_session, active_collection):
    fake = _FakeQdrantRAGClient()

    await replace_previous_ingestion(db_session, fake, active_collection, "https://exemplo.com/a")

    assert fake.deleted == []


async def test_queue_page_enfileira_com_a_sugestao_do_llm_mesmo_com_confianca_alta(
    db_session, active_collection
):
    """Nada entra no RAG sem aprovação: o LLM só sugere o domínio."""
    classification = PageClassification(domain="vendas", confidence=0.99)

    await queue_page(
        db_session, active_collection, "https://exemplo.com/confiante", "conteúdo", classification
    )

    pendentes = await list_pending_pages(db_session)
    assert len(pendentes) == 1
    assert pendentes[0].url == "https://exemplo.com/confiante"
    assert pendentes[0].domain_proposed == "vendas"
    assert pendentes[0].confidence == 0.99
    assert pendentes[0].collection_id == active_collection.id
    assert await list_documents(db_session) == []


async def test_queue_page_mesma_url_atualiza_a_linha_em_vez_de_duplicar(
    db_session, active_collection
):
    classification = PageClassification(domain="vendas", confidence=0.5)

    await queue_page(db_session, active_collection, "https://exemplo.com/p", "v1", classification)
    await queue_page(db_session, active_collection, "https://exemplo.com/p", "v2", classification)

    pendentes = await list_pending_pages(db_session)
    assert [p.extracted_text for p in pendentes] == ["v2"]


async def test_replace_previous_ingestion_apaga_a_versao_anterior_da_url(
    db_session, active_collection, tmp_path
):
    fake = _FakeQdrantRAGClient()
    embedder = EmbedderRegistry().get(active_collection.embedding_model)
    await ingest_bytes(
        fake,
        embedder,
        active_collection,
        tmp_path,
        filename="https://exemplo.com/produtos",
        content="versão 1".encode(),
        domain="vendas",
        session=db_session,
        origin="crawler",
    )
    primeiro_document_id = fake.upserts[0][4]

    await replace_previous_ingestion(
        db_session, fake, active_collection, "https://exemplo.com/produtos"
    )

    assert fake.deleted == [(active_collection.name, primeiro_document_id)]
    assert await list_documents(db_session) == []
