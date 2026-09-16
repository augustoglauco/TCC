import asyncio
import uuid

from app.rag.registry import (
    count_documents_by_collection,
    create_document,
    delete_document,
    list_documents,
    list_documents_by_collection,
)


async def _cria(session, *, collection_id, **overrides):
    defaults = dict(
        document_id=str(uuid.uuid4()),
        collection_id=collection_id,
        filename="catalogo.txt",
        domain="vendas",
        chunk_count=2,
        storage_path=None,
        origin="upload",
    )
    defaults.update(overrides)
    return await create_document(session, **defaults)


async def test_create_document_grava_e_devolve_o_documento_criado(db_session, active_collection):
    documento = await _cria(db_session, collection_id=active_collection.id, filename="a.txt")

    assert documento.filename == "a.txt"
    assert documento.collection_id == active_collection.id
    assert documento.id is not None
    assert documento.created_at is not None


async def test_list_documents_retorna_mais_recente_primeiro(db_session, active_collection):
    primeiro = await _cria(db_session, collection_id=active_collection.id, filename="primeiro.txt")
    await asyncio.sleep(1.1)  # Ensure different SQLite second precision
    segundo = await _cria(db_session, collection_id=active_collection.id, filename="segundo.txt")

    documentos = await list_documents(db_session)

    assert [d.id for d in documentos] == [segundo.id, primeiro.id]


async def test_list_documents_sem_nenhum_documento_retorna_lista_vazia(db_session):
    assert await list_documents(db_session) == []


async def test_delete_document_existente_remove_e_retorna_true(db_session, active_collection):
    documento = await _cria(db_session, collection_id=active_collection.id)

    removido = await delete_document(db_session, str(documento.id))

    assert removido is True
    assert await list_documents(db_session) == []


async def test_delete_document_inexistente_retorna_false(db_session):
    removido = await delete_document(db_session, str(uuid.uuid4()))

    assert removido is False


async def test_list_documents_by_collection_filtra_pela_collection(db_session, active_collection):
    from app.rag.collections_registry import create_collection

    outra_collection = await create_collection(
        db_session,
        name="outra",
        embedding_model="modelo-teste",
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
    await _cria(db_session, collection_id=active_collection.id, filename="da_ativa.txt")
    await _cria(db_session, collection_id=outra_collection.id, filename="da_outra.txt")

    documentos = await list_documents_by_collection(db_session, active_collection.id)

    assert [d.filename for d in documentos] == ["da_ativa.txt"]


async def test_count_documents_by_collection_agrupa_por_collection(db_session, active_collection):
    await _cria(db_session, collection_id=active_collection.id, filename="a.txt")
    await _cria(db_session, collection_id=active_collection.id, filename="b.txt")

    contagens = await count_documents_by_collection(db_session)

    assert contagens[active_collection.id] == 2
