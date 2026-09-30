"""Busca agregada em várias `RagCollection` em paralelo — extraído de
`app.mcp_server.b2b.manuais_busca` (Fase 5, R12) para ser reaproveitado
também pelo modo admin do chat (Fase 6, decisão de 2026-09-30 em
`docs/ARCHITECTURE.md` §6): os dois precisam da mesma lógica de "buscar N
collections ao mesmo tempo, tolerar falha de uma sem derrubar as demais,
agregar por score", só mudando qual conjunto de collections é passado.
"""

import asyncio
import logging

from app.db.models import RagCollection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import DEFAULT_SCORE_THRESHOLD, QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError

logger = logging.getLogger(__name__)


async def buscar_em_varias_collections(
    collections: list[RagCollection],
    qdrant: QdrantRAGClient,
    embedders: EmbedderRegistry,
    query: str,
    domain: str,
    *,
    top_k: int,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> list[tuple[RagCollection, Document]]:
    """Busca `query`/`domain` em todas as `collections` ao mesmo tempo
    (`asyncio.gather`, um round-trip por collection em vez de N sequenciais)
    e devolve os pares (collection, documento) ordenados por score
    decrescente, cortados em `top_k`. Uma collection que falhar
    (`RAGConnectionError`, ex.: Qdrant fora do ar) é ignorada e logada; as
    demais seguem normalmente."""

    async def _buscar(collection: RagCollection) -> list[Document]:
        embedder = embedders.get(collection.embedding_model)
        return await qdrant.search(
            collection.name, embedder, query, domain, top_k=top_k, score_threshold=score_threshold
        )

    buscas = await asyncio.gather(*(_buscar(c) for c in collections), return_exceptions=True)

    pares: list[tuple[RagCollection, Document]] = []
    for collection, busca in zip(collections, buscas, strict=True):
        if isinstance(busca, RAGConnectionError):
            logger.warning(
                "rag_multi_collection_busca_falhou collection=%s domain=%s erro=%s",
                collection.name,
                domain,
                busca,
            )
            continue
        if isinstance(busca, BaseException):
            raise busca
        pares.extend((collection, documento) for documento in busca)

    pares.sort(key=lambda par: par[1].score, reverse=True)
    return pares[:top_k]
