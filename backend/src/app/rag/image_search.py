"""Busca multimodal por similaridade visual via CLIP (R6) — ingestão e
busca sobre a collection `catalogo_imagens` no Qdrant.

# MVP: collection separada da collection de texto (`docs_texto`), com
# dimensão fixa 512 (CLIP ViT-B/32) e métrica cosine. Criada
# automaticamente na primeira ingestão se não existir. Reranking básico dos
# resultados implementado em `rerank_image_results` (Fase 3); sem
# deduplicação (mesmo comportamento de `QdrantRAGClient.upsert_chunks`).
"""

import logging
import uuid

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.rag.clip_embedder import CLIP_VECTOR_DIMENSION, ClipEmbedder
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

IMAGE_COLLECTION_NAME = "catalogo_imagens"
DEFAULT_TOP_K = 5
DEFAULT_SCORE_THRESHOLD = 0.20  # CLIP cosine scores são mais baixos que texto

# MVP: reranking básico (item da Fase 3, ver docs/ARCHITECTURE.md §5). O
# CLIP já devolve os resultados ordenados por score cosine; o rerank busca um
# pool maior (top_k * _RERANK_FETCH_MULTIPLIER) e reordena aplicando um bônus
# pequeno quando o domínio do resultado bate com o domínio consultado, então
# corta para top_k. Não usa cross-encoder nem segundo modelo (seria mais
# pesado e fora do "básico" pedido). Quando não há domínio na consulta, o
# rerank preserva a ordem original por score.
_RERANK_FETCH_MULTIPLIER = 3
_RERANK_DOMAIN_BONUS = 0.05


class ImageSearchResult(BaseModel):
    image_id: str
    filename: str
    domain: str
    score: float


def rerank_image_results(
    results: list[ImageSearchResult],
    query_domain: str | None,
    top_k: int,
) -> list[ImageSearchResult]:
    """Reordena resultados de busca por imagem e corta para `top_k`.

    Reranking básico (Fase 3): mantém a ordem por score do CLIP, mas dá um
    pequeno bônus (`_RERANK_DOMAIN_BONUS`) aos resultados cujo `domain` bate
    com `query_domain`, para priorizar o domínio consultado quando a busca
    trouxe um pool misto. O `score` exibido no resultado NÃO é alterado — o
    bônus é usado apenas como chave de ordenação. Sem `query_domain`, apenas
    reordena por score decrescente (estável) e corta.
    """

    def sort_key(item: ImageSearchResult) -> float:
        bonus = (
            _RERANK_DOMAIN_BONUS
            if query_domain is not None and item.domain == query_domain
            else 0.0
        )
        return item.score + bonus

    reranked = sorted(results, key=sort_key, reverse=True)
    return reranked[:top_k]


class ClipImageStore:
    """Operações de ingestão e busca sobre a collection CLIP no Qdrant.

    Cria a collection automaticamente se não existir (diferente de
    `QdrantRAGClient`, que exige criação explícita via API admin — aqui a
    collection é única e de configuração fixa, sem perfis configuráveis).
    """

    def __init__(self, qdrant_client: AsyncQdrantClient) -> None:
        self._client = qdrant_client

    async def _ensure_collection(self) -> None:
        # MVP: criação automática na primeira ingestão, sem perfil configurável
        # (dimensão 512, cosine fixos) — diferente de `QdrantRAGClient`, que
        # exige criação explícita via API admin. Aceitável porque `catalogo_imagens`
        # é uma collection única de configuração fixa neste protótipo.
        try:
            if await self._client.collection_exists(IMAGE_COLLECTION_NAME):
                return
            await self._client.create_collection(
                collection_name=IMAGE_COLLECTION_NAME,
                vectors_config=VectorParams(size=CLIP_VECTOR_DIMENSION, distance=Distance.COSINE),
            )
            logger.info("clip_collection_criada collection=%s", IMAGE_COLLECTION_NAME)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def upsert_image(
        self,
        embedder: ClipEmbedder,
        image_bytes: bytes,
        filename: str,
        domain: str,
    ) -> str:
        """Embeda e grava uma imagem. Retorna o `image_id` gerado."""
        await self._ensure_collection()
        try:
            [vector] = await embedder.embed_images([image_bytes])
            image_id = str(uuid.uuid4())
            await self._client.upsert(
                collection_name=IMAGE_COLLECTION_NAME,
                points=[
                    PointStruct(
                        id=image_id,
                        vector=vector,
                        payload={"filename": filename, "domain": domain, "image_id": image_id},
                    )
                ],
            )
        except RAGConnectionError:
            raise
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
        return image_id

    async def search_by_image(
        self,
        embedder: ClipEmbedder,
        image_bytes: bytes,
        domain: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> list[ImageSearchResult]:
        """Busca imagens similares a partir de uma imagem de consulta."""
        return await self._search(
            vector=(await embedder.embed_images([image_bytes]))[0],
            domain=domain,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    async def search_by_text(
        self,
        embedder: ClipEmbedder,
        query: str,
        domain: str | None = None,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> list[ImageSearchResult]:
        """Busca imagens similares a partir de uma descrição textual."""
        return await self._search(
            vector=(await embedder.embed_texts([query]))[0],
            domain=domain,
            top_k=top_k,
            score_threshold=score_threshold,
        )

    async def _search(
        self,
        vector: list[float],
        domain: str | None,
        top_k: int,
        score_threshold: float,
    ) -> list[ImageSearchResult]:
        try:
            if not await self._client.collection_exists(IMAGE_COLLECTION_NAME):
                return []
            query_filter = (
                Filter(must=[FieldCondition(key="domain", match=MatchValue(value=domain))])
                if domain
                else None
            )
            # Busca um pool maior que top_k para o reranking ter o que
            # reordenar (ver rerank_image_results). Quando há filtro de
            # domínio, todos os resultados já são do domínio consultado — o
            # rerank então só garante a ordem por score e o corte em top_k.
            response = await self._client.query_points(
                collection_name=IMAGE_COLLECTION_NAME,
                query=vector,
                query_filter=query_filter,
                limit=top_k * _RERANK_FETCH_MULTIPLIER,
                score_threshold=score_threshold,
            )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

        candidatos = [
            ImageSearchResult(
                image_id=point.payload["image_id"],
                filename=point.payload["filename"],
                domain=point.payload["domain"],
                score=round(point.score, 4),
            )
            for point in response.points
        ]
        return rerank_image_results(candidatos, query_domain=domain, top_k=top_k)
