"""Playground de busca comparativo entre collections (Entregas B+C+D, além
do MVP) — roda a mesma pergunta contra várias collections e devolve
resultados/score/latência lado a lado, sem agregar métrica de qualidade
(isso é a Fase 10 do roadmap). Ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.3.
"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.models.rag import (
    PlaygroundDocumentResult,
    PlaygroundResultItem,
    PlaygroundSearchRequest,
    PlaygroundSearchResponse,
)
from app.rag.collections_registry import get_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient

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
        try:
            collection = await get_collection(session, collection_id)
        except SQLAlchemyError as exc:
            # Isolamento por collection: uma falha de Postgres na busca de UMA
            # collection vira um item de erro para ela, sem abortar as demais
            # (mesmo espírito do `except Exception` abaixo, achado #2 da
            # revisão final).
            resultados.append(
                PlaygroundResultItem(
                    collection_id=collection_id, collection_name="?", error=str(exc)
                )
            )
            continue
        if collection is None:
            resultados.append(
                PlaygroundResultItem(
                    collection_id=collection_id,
                    collection_name="?",
                    error="Collection não encontrada.",
                )
            )
            continue

        inicio = time.perf_counter()
        try:
            # Achado #3 da revisão final: `embedders.get(...)` precisa estar
            # dentro do mesmo bloco de isolamento por collection que a busca
            # no Qdrant — uma falha ao carregar o modelo de embedding (id
            # inválido/renomeado, OOM no primeiro load) vira um item de erro
            # isolado para ESTA collection, sem derrubar a requisição
            # inteira do playground.
            embedder = embedders.get(collection.embedding_model)
            documentos = await qdrant.search(collection.name, embedder, body.query, body.domain)
        except Exception as exc:
            resultados.append(
                PlaygroundResultItem(
                    collection_id=collection.id, collection_name=collection.name, error=str(exc)
                )
            )
            continue
        latencia_ms = (time.perf_counter() - inicio) * 1000

        resultados.append(
            PlaygroundResultItem(
                collection_id=collection.id,
                collection_name=collection.name,
                latency_ms=latencia_ms,
                results=[
                    PlaygroundDocumentResult(
                        content=documento.content, source=documento.source, score=documento.score
                    )
                    for documento in documentos
                ],
            )
        )

    return PlaygroundSearchResponse(items=resultados)
