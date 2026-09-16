"""Playground de busca comparativo entre collections (Entregas B+C+D, além
do MVP) — roda a mesma pergunta contra várias collections e devolve
resultados/score/latência lado a lado, sem agregar métrica de qualidade
(isso é a Fase 10 do roadmap). Ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.3.
"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.models.rag import PlaygroundDocumentResult, PlaygroundResultItem, PlaygroundSearchRequest, PlaygroundSearchResponse
from app.rag.collections_registry import get_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import RAGConnectionError

router = APIRouter(prefix="/api/rag/playground", tags=["rag-playground"])


@router.post("/search", response_model=PlaygroundSearchResponse)
async def playground_search(
    body: PlaygroundSearchRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> PlaygroundSearchResponse:
    resultados: list[PlaygroundResultItem] = []

    for collection_id in body.collection_ids:
        collection = await get_collection(session, collection_id)
        if collection is None:
            resultados.append(
                PlaygroundResultItem(
                    collection_id=collection_id, collection_name="?", error="Collection não encontrada."
                )
            )
            continue

        embedder = embedders.get(collection.embedding_model)
        inicio = time.perf_counter()
        try:
            documentos = await qdrant.search(collection.name, embedder, body.query, body.domain)
        except RAGConnectionError as exc:
            resultados.append(
                PlaygroundResultItem(collection_id=collection.id, collection_name=collection.name, error=str(exc))
            )
            continue
        latencia_ms = (time.perf_counter() - inicio) * 1000

        resultados.append(
            PlaygroundResultItem(
                collection_id=collection.id,
                collection_name=collection.name,
                latency_ms=latencia_ms,
                results=[
                    PlaygroundDocumentResult(content=documento.content, source=documento.source, score=documento.score)
                    for documento in documentos
                ],
            )
        )

    return PlaygroundSearchResponse(items=resultados)
