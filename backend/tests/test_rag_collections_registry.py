import uuid

import pytest

from app.rag.collections_registry import (
    CollectionActiveError,
    activate_collection,
    create_collection,
    delete_collection,
    get_active_collection,
    get_collection,
    list_collections,
)
from app.rag.registry import create_document


async def _cria_collection(session, **overrides):
    defaults = dict(
        name=f"col_{uuid.uuid4().hex}",
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
    defaults.update(overrides)
    return await create_collection(session, **defaults)


async def test_create_collection_grava_e_devolve_a_collection_criada(db_session):
    collection = await _cria_collection(db_session, name="minha_collection")

    assert collection.name == "minha_collection"
    assert collection.is_active is False
    assert collection.id is not None


async def test_list_collections_retorna_mais_recente_primeiro(db_session):
    import asyncio

    primeira = await _cria_collection(db_session, name="primeira")
    await asyncio.sleep(1.1)  # garante segundo diferente no SQLite
    segunda = await _cria_collection(db_session, name="segunda")

    collections = await list_collections(db_session)

    assert [c.id for c in collections] == [segunda.id, primeira.id]


async def test_get_collection_inexistente_retorna_none(db_session):
    assert await get_collection(db_session, uuid.uuid4()) is None


async def test_get_active_collection_sem_nenhuma_ativa_retorna_none(db_session):
    await _cria_collection(db_session, is_active=False)

    assert await get_active_collection(db_session) is None


async def test_activate_collection_ativa_a_escolhida_e_desativa_as_demais(db_session):
    primeira = await _cria_collection(db_session, name="primeira", is_active=True)
    segunda = await _cria_collection(db_session, name="segunda", is_active=False)

    ativado = await activate_collection(db_session, segunda.id)

    assert ativado is True
    assert (await get_active_collection(db_session)).id == segunda.id
    await db_session.refresh(primeira)
    assert primeira.is_active is False


async def test_activate_collection_inexistente_retorna_false(db_session):
    assert await activate_collection(db_session, uuid.uuid4()) is False


async def test_delete_collection_inexistente_retorna_false(db_session):
    assert await delete_collection(db_session, uuid.uuid4()) is False


async def test_delete_collection_ativa_levanta_collection_active_error(db_session):
    collection = await _cria_collection(db_session, is_active=True)

    with pytest.raises(CollectionActiveError):
        await delete_collection(db_session, collection.id)


async def test_delete_collection_inativa_remove_e_retorna_true(db_session):
    collection = await _cria_collection(db_session, is_active=False)

    removida = await delete_collection(db_session, collection.id)

    assert removida is True
    assert await get_collection(db_session, collection.id) is None


async def test_delete_collection_remove_documentos_em_cascata(db_session):
    collection = await _cria_collection(db_session, is_active=False)
    await create_document(
        db_session,
        document_id=str(uuid.uuid4()),
        collection_id=collection.id,
        filename="a.txt",
        domain="vendas",
        chunk_count=1,
        storage_path=None,
        origin="upload",
    )

    await delete_collection(db_session, collection.id)

    from app.rag.registry import list_documents

    assert await list_documents(db_session) == []
