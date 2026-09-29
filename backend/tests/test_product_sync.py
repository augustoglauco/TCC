from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.db.catalog import atualizar_estoque, criar_produto
from app.db.models import RagDocument
from app.rag.product_sync import remover_produto_do_rag, sync_produto_no_rag
from tests.conftest import _FakeQdrantRAGClient


class _EmbedderRegistryStub:
    """Substitui `EmbedderRegistry` nos testes: sempre devolve o mesmo
    `text_embedder` real, independentemente do nome do modelo pedido — a
    fixture `active_collection` usa um `embedding_model` fake que não
    existe de verdade."""

    def __init__(self, embedder):
        self._embedder = embedder

    def get(self, model_name: str):
        return self._embedder


async def _produto_padrao(session, **overrides):
    dados = dict(
        nome="Gerador Diesel GD-15",
        descricao="Potência de 15 kVA.",
        preco=Decimal("24900.00"),
        categoria="geradores",
    )
    dados.update(overrides)
    return await criar_produto(session, **dados)


async def test_sync_produto_no_rag_ingere_documento_na_collection_ativa(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    produto = await _produto_padrao(db_session)
    qdrant = _FakeQdrantRAGClient()
    embedders = _EmbedderRegistryStub(text_embedder)

    await sync_produto_no_rag(db_session, qdrant, embedders, tmp_path / "uploads", produto)

    assert len(qdrant.upserts) == 1
    collection_name, chunks, source, domain, _document_id = qdrant.upserts[0]
    assert collection_name == active_collection.name
    assert source == f"produto_{produto.id}.txt"
    assert domain == "vendas"
    assert "Gerador Diesel GD-15" in chunks[0]
    result = await db_session.execute(select(RagDocument).where(RagDocument.filename == source))
    assert len(result.scalars().all()) == 1


async def test_sync_produto_no_rag_reingesta_sem_duplicar_documento(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    produto = await _produto_padrao(db_session)
    qdrant = _FakeQdrantRAGClient()
    embedders = _EmbedderRegistryStub(text_embedder)
    uploads_dir = tmp_path / "uploads"
    filename = f"produto_{produto.id}.txt"

    await sync_produto_no_rag(db_session, qdrant, embedders, uploads_dir, produto)
    await atualizar_estoque(db_session, produto.id, "CD-SP", 7)
    await db_session.refresh(produto, attribute_names=["estoques"])
    await sync_produto_no_rag(db_session, qdrant, embedders, uploads_dir, produto)

    result = await db_session.execute(select(RagDocument).where(RagDocument.filename == filename))
    documentos = result.scalars().all()
    assert len(documentos) == 1  # reingestão não duplica o documento
    assert len(qdrant.upserts) == 2  # duas ingestões...
    assert len(qdrant.deleted) == 1  # ...mas a segunda apaga a primeira antes
    _collection_name, chunks_segunda_ingestao, *_ = qdrant.upserts[1]
    assert "estoque_total: 7" in chunks_segunda_ingestao[0]


async def test_sync_produto_no_rag_sem_collection_ativa_nao_levanta(
    tmp_path: Path, db_session, text_embedder
):
    # Sem `active_collection`: nenhuma RagCollection ativa no banco.
    produto = await _produto_padrao(db_session)
    qdrant = _FakeQdrantRAGClient()
    embedders = _EmbedderRegistryStub(text_embedder)

    await sync_produto_no_rag(db_session, qdrant, embedders, tmp_path / "uploads", produto)

    assert qdrant.upserts == []


async def test_sync_produto_no_rag_falha_no_qdrant_nao_propaga(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    produto = await _produto_padrao(db_session)
    qdrant = _FakeQdrantRAGClient(error=RuntimeError("qdrant indisponível"))
    embedders = _EmbedderRegistryStub(text_embedder)

    # Não levanta — falha de sincronização no RAG nunca pode derrubar o CRUD
    # de produtos (fonte de verdade é o SQL, não o RAG).
    await sync_produto_no_rag(db_session, qdrant, embedders, tmp_path / "uploads", produto)


async def test_remover_produto_do_rag_apaga_documento_existente(
    tmp_path: Path, db_session, active_collection, text_embedder
):
    produto = await _produto_padrao(db_session)
    qdrant = _FakeQdrantRAGClient()
    embedders = _EmbedderRegistryStub(text_embedder)
    filename = f"produto_{produto.id}.txt"
    await sync_produto_no_rag(db_session, qdrant, embedders, tmp_path / "uploads", produto)

    await remover_produto_do_rag(db_session, qdrant, produto.id)

    assert len(qdrant.deleted) == 1
    result = await db_session.execute(select(RagDocument).where(RagDocument.filename == filename))
    assert result.scalars().all() == []


async def test_remover_produto_do_rag_sem_documento_nao_levanta(
    tmp_path: Path, db_session, active_collection
):
    qdrant = _FakeQdrantRAGClient()

    await remover_produto_do_rag(db_session, qdrant, produto_id=999)

    assert qdrant.deleted == []
