import uuid

from app.rag.registry import create_document, delete_document, list_documents


async def _cria(session, **overrides):
    defaults = dict(
        document_id=str(uuid.uuid4()),
        filename="catalogo.txt",
        domain="vendas",
        chunk_count=2,
        embedding_model="modelo-teste",
        chunk_size=800,
        chunk_overlap=100,
        origin="upload",
    )
    defaults.update(overrides)
    return await create_document(session, **defaults)


async def test_create_document_grava_e_devolve_o_documento_criado(db_session):
    documento = await _cria(db_session, filename="a.txt")

    assert documento.filename == "a.txt"
    assert documento.id is not None
    assert documento.created_at is not None


async def test_list_documents_retorna_mais_recente_primeiro(db_session):
    primeiro = await _cria(db_session, filename="primeiro.txt")
    segundo = await _cria(db_session, filename="segundo.txt")

    documentos = await list_documents(db_session)

    assert [d.id for d in documentos] == [segundo.id, primeiro.id]


async def test_list_documents_sem_nenhum_documento_retorna_lista_vazia(db_session):
    assert await list_documents(db_session) == []


async def test_delete_document_existente_remove_e_retorna_true(db_session):
    documento = await _cria(db_session)

    removido = await delete_document(db_session, str(documento.id))

    assert removido is True
    assert await list_documents(db_session) == []


async def test_delete_document_inexistente_retorna_false(db_session):
    removido = await delete_document(db_session, str(uuid.uuid4()))

    assert removido is False
