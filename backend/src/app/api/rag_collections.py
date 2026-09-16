"""Endpoints HTTP de perfis de collection do RAG (Entregas B+C+D, além do
MVP): criação, listagem, ativação e exclusão em cascata.

Ver docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.1.
"""

import logging
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session, get_embedder_registry, get_qdrant_client
from app.models.rag import CollectionCreateRequest, CollectionResponse
from app.rag.collections_registry import (
    CollectionActiveError,
    activate_collection,
    create_collection,
    delete_collection,
    get_collection,
    get_collection_by_name,
    list_collections,
)
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import CollectionAlreadyExistsError, QdrantRAGClient
from app.rag.registry import count_documents_by_collection, list_documents_by_collection
from app.router.rag_client import RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag/collections", tags=["rag-collections"])


def _quantization_config_dict(quantization) -> dict:
    if quantization.type == "scalar" and quantization.scalar is not None:
        return quantization.scalar.model_dump()
    if quantization.type == "product" and quantization.product is not None:
        return quantization.product.model_dump()
    if quantization.type == "binary" and quantization.binary is not None:
        return quantization.binary.model_dump()
    return {}


def _to_response(collection, document_count: int) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        name=collection.name,
        embedding_model=collection.embedding_model,
        vector_dimension=collection.vector_dimension,
        distance_metric=collection.distance_metric,
        chunk_size=collection.chunk_size,
        chunk_overlap=collection.chunk_overlap,
        hnsw_m=collection.hnsw_m,
        hnsw_ef_construct=collection.hnsw_ef_construct,
        hnsw_full_scan_threshold=collection.hnsw_full_scan_threshold,
        hnsw_max_indexing_threads=collection.hnsw_max_indexing_threads,
        hnsw_on_disk=collection.hnsw_on_disk,
        hnsw_payload_m=collection.hnsw_payload_m,
        quantization_type=collection.quantization_type,
        quantization_config=collection.quantization_config,
        payload_indexes=collection.payload_indexes,
        is_active=collection.is_active,
        document_count=document_count,
        created_at=collection.created_at,
    )


@router.post("", response_model=CollectionResponse)
async def create_collection_endpoint(
    body: CollectionCreateRequest,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    embedders: EmbedderRegistry = Depends(get_embedder_registry),
    session: AsyncSession = Depends(get_db_session),
) -> CollectionResponse:
    # Limpeza da revisão final: checagem de nome duplicado é barata (uma
    # consulta ao Postgres) e deve rodar antes de `embedder.get_dimension()`,
    # que pode ser cara (carrega o modelo de embedding na primeira chamada).
    existing = await get_collection_by_name(session, body.name)
    if existing is not None:
        raise HTTPException(
            status_code=409, detail=f"Já existe uma collection chamada '{body.name}'."
        )

    embedder = embedders.get(body.embedding_model)
    try:
        dimension = await embedder.get_dimension()
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Não foi possível carregar o modelo de embedding: {exc}"
        ) from exc

    payload_indexes = [item.model_dump() for item in body.payload_indexes]
    quantization_config = _quantization_config_dict(body.quantization)

    try:
        await qdrant.create_collection(
            name=body.name,
            vector_dimension=dimension,
            distance_metric=body.distance_metric,
            hnsw_m=body.hnsw.m,
            hnsw_ef_construct=body.hnsw.ef_construct,
            hnsw_full_scan_threshold=body.hnsw.full_scan_threshold,
            hnsw_max_indexing_threads=body.hnsw.max_indexing_threads,
            hnsw_on_disk=body.hnsw.on_disk,
            hnsw_payload_m=body.hnsw.payload_m,
            quantization_type=body.quantization.type,
            quantization_config=quantization_config,
            payload_indexes=payload_indexes,
        )
    except CollectionAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409, detail=f"Já existe uma collection chamada '{body.name}'."
        ) from exc
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    try:
        collection = await create_collection(
            session,
            name=body.name,
            embedding_model=body.embedding_model,
            vector_dimension=dimension,
            distance_metric=body.distance_metric,
            chunk_size=body.chunk_size,
            chunk_overlap=body.chunk_overlap,
            hnsw_m=body.hnsw.m,
            hnsw_ef_construct=body.hnsw.ef_construct,
            hnsw_full_scan_threshold=body.hnsw.full_scan_threshold,
            hnsw_max_indexing_threads=body.hnsw.max_indexing_threads,
            hnsw_on_disk=body.hnsw.on_disk,
            hnsw_payload_m=body.hnsw.payload_m,
            quantization_type=body.quantization.type,
            quantization_config=quantization_config,
            payload_indexes=payload_indexes,
        )
    except SQLAlchemyError as exc:
        # Achado #1 da revisão final: o registro no Postgres falhou depois
        # do Qdrant já ter criado a collection — sem rollback, ela fica
        # órfã (existe no Qdrant, invisível via `list_collections`, e um
        # retry com o mesmo nome esbarraria num 409 permanente). Tenta
        # desfazer a criação no Qdrant antes de propagar o erro.
        try:
            await qdrant.drop_collection(body.name)
        except RAGConnectionError:
            logger.warning(
                "rag_collection_orfa nome=%s — collection criada no Qdrant sem registro "
                "correspondente no Postgres, e o rollback (exclusão da collection no Qdrant) "
                "também falhou; limpeza manual necessária",
                body.name,
            )
        else:
            logger.warning(
                "rag_collection_orfa nome=%s — collection criada no Qdrant sem registro "
                "correspondente no Postgres; rollback (exclusão da collection no Qdrant) "
                "executado com sucesso",
                body.name,
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de collections temporariamente indisponível, tente novamente."
            ),
        ) from exc

    return _to_response(collection, document_count=0)


@router.get("", response_model=list[CollectionResponse])
async def list_collections_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> list[CollectionResponse]:
    try:
        collections = await list_collections(session)
        counts = await count_documents_by_collection(session)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_collections_indisponivel",
            extra={"rag": {"event": "rag_collections_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de collections temporariamente indisponível, tente novamente."
            ),
        ) from exc
    return [_to_response(collection, counts.get(collection.id, 0)) for collection in collections]


@router.post("/{collection_id}/activate", status_code=204)
async def activate_collection_endpoint(
    collection_id: UUID, session: AsyncSession = Depends(get_db_session)
) -> None:
    try:
        ativado = await activate_collection(session, collection_id)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_collections_indisponivel",
            extra={"rag": {"event": "rag_collections_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de collections temporariamente indisponível, tente novamente."
            ),
        ) from exc
    if not ativado:
        raise HTTPException(status_code=404, detail="Collection não encontrada.")


@router.delete("/{collection_id}", status_code=204)
async def delete_collection_endpoint(
    collection_id: UUID,
    qdrant: QdrantRAGClient = Depends(get_qdrant_client),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        # Limpeza da revisão final: `get_collection` (busca O(1) por chave
        # primária) substitui a varredura O(n) em Python sobre
        # `list_collections` que existia aqui antes.
        collection = await get_collection(session, collection_id)
        if collection is None:
            raise HTTPException(status_code=404, detail="Collection não encontrada.")
        if collection.is_active:
            raise HTTPException(
                status_code=409,
                detail=("Não é possível excluir a collection ativa. Ative outra collection antes."),
            )

        documentos = await list_documents_by_collection(session, collection_id)
    except SQLAlchemyError as exc:
        logger.error(
            "rag_collections_indisponivel",
            extra={"rag": {"event": "rag_collections_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de collections temporariamente indisponível, tente novamente."
            ),
        ) from exc

    try:
        await qdrant.drop_collection(collection.name)
    except RAGConnectionError as exc:
        raise HTTPException(
            status_code=503, detail="Serviço de RAG temporariamente indisponível, tente novamente."
        ) from exc

    for documento in documentos:
        if documento.storage_path is not None:
            Path(documento.storage_path).unlink(missing_ok=True)

    try:
        await delete_collection(session, collection_id)
    except CollectionActiveError as exc:
        raise HTTPException(
            status_code=409, detail="Não é possível excluir a collection ativa."
        ) from exc
    except SQLAlchemyError as exc:
        # Achado #2 da revisão final: diferente do caminho de criação, aqui
        # o Qdrant já foi apagado com sucesso ANTES desta etapa — se o
        # Postgres falhar agora, a linha de `RagCollection`/`RagDocument`
        # sobrevive apontando para uma collection que não existe mais no
        # Qdrant (órfã no sentido oposto do achado #1). Mesmo padrão de log
        # (`rag_collection_orfa`) usado lá.
        logger.warning(
            "rag_collection_orfa id=%s nome=%s — collection já removida do Qdrant, mas o "
            "registro no Postgres não pôde ser removido (drift entre os dois stores)",
            collection.id,
            collection.name,
        )
        logger.error(
            "rag_collections_indisponivel",
            extra={"rag": {"event": "rag_collections_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Serviço de registro de collections temporariamente indisponível, tente novamente."
            ),
        ) from exc
