"""Testes para app.rag.clip_embedder e app.rag.image_search (R6, Fase 3)."""

import io

import pytest
from qdrant_client import AsyncQdrantClient

from app.rag.clip_embedder import CLIP_VECTOR_DIMENSION, ClipEmbedder
from app.rag.image_search import (
    IMAGE_COLLECTION_NAME,
    ClipImageStore,
    ImageSearchResult,
    rerank_image_results,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes() -> bytes:
    """PNG mínimo válido (1×1 pixel branco) para testes sem GPU."""
    pytest.importorskip("PIL", reason="Pillow não instalado")
    from PIL import Image

    img = Image.new("RGB", (4, 4), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# ClipEmbedder
# ---------------------------------------------------------------------------


@pytest.mark.gpu
async def test_clip_embed_images_retorna_vetor_correto():
    embedder = ClipEmbedder()
    png = _make_png_bytes()
    vectors = await embedder.embed_images([png])
    assert len(vectors) == 1
    assert len(vectors[0]) == CLIP_VECTOR_DIMENSION


@pytest.mark.gpu
async def test_clip_embed_texts_retorna_vetor_correto():
    embedder = ClipEmbedder()
    vectors = await embedder.embed_texts(["gerador a diesel"])
    assert len(vectors) == 1
    assert len(vectors[0]) == CLIP_VECTOR_DIMENSION


async def test_clip_embed_lista_vazia():
    embedder = ClipEmbedder()
    assert await embedder.embed_images([]) == []
    assert await embedder.embed_texts([]) == []


async def test_clip_embed_images_bytes_invalidos_levanta_erro_tipado():
    """Bytes que não são imagem devem virar InvalidImageError (não
    UnidentifiedImageError cru) — root cause do bug 2026-09-20. Exercita o
    PIL real, sem GPU (falha antes de tocar no modelo)."""
    from app.rag.clip_embedder import InvalidImageError

    embedder = ClipEmbedder()
    with pytest.raises(InvalidImageError):
        await embedder.embed_images([b"isto-nao-e-uma-imagem"])


# ---------------------------------------------------------------------------
# ClipImageStore (com Qdrant em memória)
# ---------------------------------------------------------------------------


@pytest.fixture
def qdrant_in_memory():
    return AsyncQdrantClient(location=":memory:")


@pytest.fixture
def fake_embedder(monkeypatch):
    """ClipEmbedder com embed_images/embed_texts substituídos por vetores
    determinísticos — sem GPU nem modelo real."""
    embedder = ClipEmbedder.__new__(ClipEmbedder)

    async def _fake_images(images):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in images]

    async def _fake_texts(texts):
        return [[0.1] * CLIP_VECTOR_DIMENSION for _ in texts]

    embedder.embed_images = _fake_images
    embedder.embed_texts = _fake_texts
    return embedder


async def test_upsert_e_search_by_text(qdrant_in_memory, fake_embedder):
    store = ClipImageStore(qdrant_in_memory)
    png = _make_png_bytes()

    image_id = await store.upsert_image(fake_embedder, png, filename="prod.png", domain="vendas")
    assert image_id  # UUID gerado

    results = await store.search_by_text(fake_embedder, "gerador", domain="vendas")
    assert len(results) == 1
    assert results[0].filename == "prod.png"
    assert results[0].domain == "vendas"


async def test_upsert_e_search_by_image(qdrant_in_memory, fake_embedder):
    store = ClipImageStore(qdrant_in_memory)
    png = _make_png_bytes()

    await store.upsert_image(fake_embedder, png, filename="prod.png", domain="vendas")
    results = await store.search_by_image(fake_embedder, png, domain="vendas")
    assert len(results) >= 1


async def test_search_sem_collection_retorna_vazio(qdrant_in_memory, fake_embedder):
    """Busca antes de qualquer ingestão deve retornar lista vazia."""
    store = ClipImageStore(qdrant_in_memory)
    results = await store.search_by_text(fake_embedder, "qualquer coisa")
    assert results == []


async def test_collection_criada_automaticamente(qdrant_in_memory, fake_embedder):
    store = ClipImageStore(qdrant_in_memory)
    png = _make_png_bytes()
    await store.upsert_image(fake_embedder, png, filename="x.png", domain="vendas")
    assert await qdrant_in_memory.collection_exists(IMAGE_COLLECTION_NAME)


async def test_filtro_por_domain(qdrant_in_memory, fake_embedder):
    """Imagem ingerida em 'suporte' não deve aparecer em busca por 'vendas'."""
    store = ClipImageStore(qdrant_in_memory)
    png = _make_png_bytes()
    await store.upsert_image(fake_embedder, png, filename="manual.png", domain="suporte")
    results = await store.search_by_text(fake_embedder, "qualquer", domain="vendas")
    assert results == []


# ---------------------------------------------------------------------------
# rerank_image_results (reranking básico, Fase 3)
# ---------------------------------------------------------------------------


def _result(image_id: str, domain: str, score: float) -> ImageSearchResult:
    return ImageSearchResult(
        image_id=image_id, filename=f"{image_id}.png", domain=domain, score=score
    )


def test_rerank_sem_dominio_preserva_ordem_por_score_e_corta():
    results = [
        _result("a", "vendas", 0.90),
        _result("b", "suporte", 0.80),
        _result("c", "vendas", 0.70),
    ]
    reranked = rerank_image_results(results, query_domain=None, top_k=2)
    assert [r.image_id for r in reranked] == ["a", "b"]


def test_rerank_da_bonus_ao_dominio_consultado():
    # 'c' (vendas, 0.70) recebe bônus 0.05 -> 0.75, ultrapassando
    # 'b' (suporte, 0.72) na ordenação, mesmo com score bruto menor.
    results = [
        _result("a", "vendas", 0.90),
        _result("b", "suporte", 0.72),
        _result("c", "vendas", 0.70),
    ]
    reranked = rerank_image_results(results, query_domain="vendas", top_k=3)
    assert [r.image_id for r in reranked] == ["a", "c", "b"]


def test_rerank_nao_altera_o_score_exibido():
    results = [_result("c", "vendas", 0.70)]
    reranked = rerank_image_results(results, query_domain="vendas", top_k=1)
    # O bônus é só chave de ordenação — o score reportado continua o original.
    assert reranked[0].score == 0.70


def test_rerank_lista_vazia():
    assert rerank_image_results([], query_domain="vendas", top_k=5) == []
