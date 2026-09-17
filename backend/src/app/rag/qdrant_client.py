"""Cliente RAG real via Qdrant (R4) — ingestão e busca vetorial de texto/PDF.

Desde a entrega de perfis de collection configuráveis (ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md), esta
classe não guarda mais "a" collection fixa: cada operação recebe
explicitamente o nome da collection (e, quando aplicável, o embedder usado
por ela), porque o sistema agora suporta múltiplas collections com perfis
diferentes (ver `app.rag.collections_registry.RagCollection`). Coleções
precisam existir antes de qualquer ingestão/busca — são sempre criadas
explicitamente via `create_collection` (endpoint `POST /api/rag/collections`),
nunca implicitamente na primeira ingestão como antes desta entrega.

O contrato `RAGClient` Protocol (busca usada pelo orchestrator) é
implementado por `app.rag.active_collection_client.ActiveCollectionRagClient`,
não por esta classe diretamente — ver
docs/superpowers/specs/2026-09-05-roteador-basico-design.md §2.3 para a
origem do Protocol.
"""

import asyncio
import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    BinaryQuantization,
    BinaryQuantizationConfig,
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    PointStruct,
    ProductQuantization,
    ProductQuantizationConfig,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    TextIndexParams,
    TextIndexType,
    VectorParams,
)

from app.rag.embeddings import TextEmbedder
from app.router.rag_client import Document, RAGConnectionError

logger = logging.getLogger(__name__)

# MVP: top-k e limiar de score fixos por config, sem reranking (BM25 +
# similaridade combinada é evolução futura, ver docs/TECHNOLOGY_STACK.md,
# linha "Reranking") nem configuráveis por perfil de collection (ver
# docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §10).
DEFAULT_TOP_K = 3
DEFAULT_SCORE_THRESHOLD = 0.35
# O default da própria lib qdrant-client é 5s; nesta máquina de dev (WSL2),
# resolver "localhost" ocasionalmente demora mais que isso (tentativa de
# IPv6 antes de cair para IPv4), estourando o timeout default por uma
# lentidão de rede local, não uma falha real de infraestrutura — daí um
# default um pouco mais folgado aqui.
DEFAULT_TIMEOUT_S = 10.0

_DISTANCE_BY_METRIC = {
    "cosine": Distance.COSINE,
    "euclid": Distance.EUCLID,
    "dot": Distance.DOT,
    "manhattan": Distance.MANHATTAN,
}


class CollectionAlreadyExistsError(Exception):
    """Levantada por `create_collection` quando já existe uma collection com esse nome."""


def _quantization_from_config(quantization_type: str, quantization_config: dict):
    if quantization_type == "scalar":
        return ScalarQuantization(
            scalar=ScalarQuantizationConfig(
                type=ScalarType.INT8,
                quantile=quantization_config.get("quantile", 0.99),
                always_ram=quantization_config.get("always_ram", False),
            )
        )
    if quantization_type == "product":
        return ProductQuantization(
            product=ProductQuantizationConfig(
                compression=quantization_config.get("compression", "x16"),
                always_ram=quantization_config.get("always_ram", False),
            )
        )
    if quantization_type == "binary":
        return BinaryQuantization(
            binary=BinaryQuantizationConfig(always_ram=quantization_config.get("always_ram", False))
        )
    return None


def _payload_schema_from_index(payload_index: dict):
    schema_type = payload_index["schema_type"]
    if schema_type != "text":
        return schema_type
    text_params = payload_index.get("text_params") or {}
    return TextIndexParams(
        type=TextIndexType.TEXT,
        tokenizer=text_params.get("tokenizer", "word"),
        min_token_len=text_params.get("min_token_len"),
        max_token_len=text_params.get("max_token_len"),
        lowercase=text_params.get("lowercase", True),
    )


class QdrantRAGClient:
    """Operações de baixo nível sobre o Qdrant, parametrizadas por collection.

    Não guarda estado de qual collection é "a" collection — cada método
    recebe `collection_name` (e `embedder`, quando a operação envolve gerar
    vetores) explicitamente. Ver docstring do módulo.
    """

    def __init__(
        self,
        host: str,
        port: int,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: AsyncQdrantClient | None = None,
        search_domain_fallback: bool = False,
    ) -> None:
        # Ver `Settings.rag_search_domain_fallback` (app.config) — desligado
        # por padrão porque quebra o isolamento entre domínios e o sinal de
        # escalonamento do roteador (RAG vazio → externo) documentado em
        # docs/ARCHITECTURE.md. Existe como flag para comparação/experimento.
        self._search_domain_fallback = search_domain_fallback
        self._client = (
            client
            if client is not None
            else AsyncQdrantClient(host=host, port=port, timeout=int(timeout_s))
        )
        # Achado #7 da revisão final: guarda a corrida TOCTOU entre a
        # checagem `collection_exists` e a criação de fato dentro de
        # `create_collection` — sem isso, duas requisições concorrentes de
        # criação com o mesmo nome podiam ambas ver `exists=False` e colidir
        # na criação, caindo no `except Exception -> RAGConnectionError`
        # genérico em vez do `CollectionAlreadyExistsError`/409 pretendido.
        # Um único lock por instância (não por nome) é a abordagem mais
        # simples: criação de collection é uma operação administrativa rara,
        # não um caminho quente como busca/upsert — serializar todas as
        # criações desta instância entre si é uma perda de concorrência
        # desprezível. MVP: só dentro do processo (um único worker Uvicorn),
        # não entre múltiplas instâncias do backend — ver decisão registrada
        # em docs/ARCHITECTURE.md §5.
        self._create_lock = asyncio.Lock()

    async def collection_exists(self, collection_name: str) -> bool:
        try:
            return await self._client.collection_exists(collection_name)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def create_collection(
        self,
        *,
        name: str,
        vector_dimension: int,
        distance_metric: str,
        hnsw_m: int,
        hnsw_ef_construct: int,
        hnsw_full_scan_threshold: int,
        hnsw_max_indexing_threads: int,
        hnsw_on_disk: bool,
        hnsw_payload_m: int | None,
        quantization_type: str,
        quantization_config: dict,
        payload_indexes: list[dict],
    ) -> None:
        """Cria a collection com os parâmetros completos do perfil.

        Levanta `CollectionAlreadyExistsError` se já existir uma collection
        com esse nome (checagem explícita antes de criar, em vez de deixar o
        Qdrant levantar seu próprio erro genérico de conflito).

        # MVP: sem cache de "collection existe" por nome — ao contrário da
        # versão anterior desta classe (`ensure_collection`/`_collection_ready`),
        # múltiplas collections agora podem ser criadas/excluídas em runtime
        # via API, e um cache sem invalidação abriria uma janela de
        # inconsistência (achar que uma collection excluída ainda existe).
        """
        try:
            async with self._create_lock:
                if await self._client.collection_exists(name):
                    raise CollectionAlreadyExistsError(name)
                await self._client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=vector_dimension, distance=_DISTANCE_BY_METRIC[distance_metric]
                    ),
                    hnsw_config=HnswConfigDiff(
                        m=hnsw_m,
                        ef_construct=hnsw_ef_construct,
                        full_scan_threshold=hnsw_full_scan_threshold,
                        max_indexing_threads=hnsw_max_indexing_threads,
                        on_disk=hnsw_on_disk,
                        payload_m=hnsw_payload_m,
                    ),
                    quantization_config=_quantization_from_config(
                        quantization_type, quantization_config
                    ),
                )
                for payload_index in payload_indexes:
                    await self._client.create_payload_index(
                        collection_name=name,
                        field_name=payload_index["field"],
                        field_schema=_payload_schema_from_index(payload_index),
                    )
        except CollectionAlreadyExistsError:
            raise
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def drop_collection(self, collection_name: str) -> None:
        """Remove `collection_name` do Qdrant.

        Idempotente: se a collection já não existir (drift entre Qdrant e
        Postgres, ou exclusão repetida após uma falha parcial), é um no-op
        silencioso em vez de propagar erro — mesmo espírito de
        `search`/`delete_by_document_id` nesta classe.
        """
        try:
            if not await self._client.collection_exists(collection_name):
                return
            await self._client.delete_collection(collection_name)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def upsert_chunks(
        self,
        collection_name: str,
        embedder: TextEmbedder,
        chunks: list[str],
        source: str,
        domain: str,
        document_id: str,
    ) -> int:
        """Embeda e grava `chunks` em `collection_name`, com payload
        `source`/`domain`/`document_id`.

        # MVP: sem deduplicação nem re-ingestão incremental — reingerir a
        # mesma fonte duas vezes cria pontos duplicados na collection.
        Pressupõe que `collection_name` já existe (criada via
        `create_collection`) — sem criação implícita.
        """
        if not chunks:
            return 0
        try:
            vectors = await embedder.embed(chunks)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={
                        "content": chunk,
                        "source": source,
                        "domain": domain,
                        "document_id": document_id,
                    },
                )
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            await self._client.upsert(collection_name=collection_name, points=points)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
        return len(points)

    async def search(
        self,
        collection_name: str,
        embedder: TextEmbedder,
        query: str,
        domain: str,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
    ) -> list[Document]:
        """Busca por similaridade em `collection_name`, filtrada por `domain`.

        Lista vazia é devolvida tanto quando a collection ainda não existe
        quanto quando a busca roda normalmente e não acha nada acima do
        limiar — os dois são sinal de negócio válido (o segundo é o sinal
        que o roteador usa para escalar pro modelo externo, ver
        docs/ARCHITECTURE.md). Falha de infraestrutura vira
        `RAGConnectionError`.

        Se `search_domain_fallback=True` foi passado no construtor
        (`Settings.rag_search_domain_fallback`, desligado por padrão), uma
        busca filtrada sem resultado tenta de novo SEM o filtro de domínio
        antes de devolver — sacrifica o isolamento entre domínios e o sinal
        de escalonamento acima em troca de nunca devolver vazio. Existe só
        para comparação/experimento, não é o comportamento recomendado.
        """
        try:
            if not await self._client.collection_exists(collection_name):
                return []
            [query_vector] = await embedder.embed([query])
            domain_filter = Filter(
                must=[FieldCondition(key="domain", match=MatchValue(value=domain))]
            )
            response = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                query_filter=domain_filter,
                limit=top_k,
                score_threshold=score_threshold,
            )
            if not response.points and self._search_domain_fallback:
                response = await self._client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    limit=top_k,
                    score_threshold=score_threshold,
                )
            return [
                Document(
                    content=point.payload["content"],
                    source=point.payload["source"],
                    score=point.score,
                )
                for point in response.points
            ]

        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def delete_by_document_id(self, collection_name: str, document_id: str) -> None:
        """Remove todos os pontos com aquele `document_id` no payload de
        `collection_name`."""
        try:
            if not await self._client.collection_exists(collection_name):
                return
            await self._client.delete(
                collection_name=collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
