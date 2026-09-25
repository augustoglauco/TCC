import pytest
from unittest.mock import AsyncMock
from qdrant_client import AsyncQdrantClient
from app.rag.image_search import ClipImageStore

@pytest.mark.asyncio
async def test_clip_image_store_upsert_e_delete_com_produto_id():
    client = AsyncQdrantClient(location=":memory:")
    store = ClipImageStore(client)

    embedder = AsyncMock()
    embedder.embed_images = AsyncMock(return_value=[[0.1] * 512])

    image_id = await store.upsert_image(
        embedder=embedder,
        image_bytes=b"fake-bytes",
        filename="Camera VIP",
        domain="vendas",
        produto_id=42,
        imagem_url="/api/uploads/produtos/cam.png",
    )
    assert image_id is not None

    # Busca confirma payload enriquecido
    results = await store.search_by_image(embedder, b"fake-bytes", domain="vendas")
    assert len(results) >= 1
    assert results[0].produto_id == 42
    assert results[0].imagem_url == "/api/uploads/produtos/cam.png"

    # Exclui imagem
    deleted = await store.delete_image(image_id)
    assert deleted is True

    # Busca após delete retorna vazio
    after_delete = await store.search_by_image(embedder, b"fake-bytes", domain="vendas")
    assert len(after_delete) == 0
