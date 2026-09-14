"""Cliente RAG real via Qdrant (R4) — ingestão e busca vetorial de texto/PDF.

O contrato (`RAGClient` Protocol, `Document`, `RAGConnectionError`) foi
definido em `app.router.rag_client` já na Fase 1 (ver
docs/superpowers/specs/2026-09-05-roteador-basico-design.md §2.3), para que
o orchestrator fosse testável antes do RAG real existir. Esta classe é a
implementação concreta (ingestão + busca), no módulo `app/rag/` conforme a
estrutura de pastas de docs/CONVENTIONS.md.
"""

import logging
import uuid

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.rag.embeddings import TextEmbedder
from app.router.rag_client import Document, RAGConnectionError

logger = logging.getLogger(__name__)

# Collection citada em docs/CONVENTIONS.md e docs/TECHNOLOGY_STACK.md
# ("Collections: docs_texto, catalogo_imagens") — esta classe cobre só a de
# texto; `catalogo_imagens` é RAG multimodal, Fase 3.
DEFAULT_COLLECTION_NAME = "docs_texto"

# MVP: top-k e limiar de score fixos por config, sem reranking (BM25 +
# similaridade combinada é evolução futura, ver docs/TECHNOLOGY_STACK.md,
# linha "Reranking").
DEFAULT_TOP_K = 3
DEFAULT_SCORE_THRESHOLD = 0.35
# O default da própria lib qdrant-client é 5s; nesta máquina de dev (WSL2),
# resolver "localhost" ocasionalmente demora mais que isso (tentativa de
# IPv6 antes de cair para IPv4), estourando o timeout default por uma
# lentidão de rede local, não uma falha real de infraestrutura — daí um
# default um pouco mais folgado aqui.
DEFAULT_TIMEOUT_S = 10.0


class QdrantRAGClient:
    """Implementa `RAGClient` (busca) e expõe ingestão (`upsert_chunks`).

    Filtra por `domain` via payload filtering nativo do Qdrant (ver
    docs/CONVENTIONS.md), coerente com os domínios do classificador
    (vendas/suporte/atendimento).
    """

    def __init__(
        self,
        host: str,
        port: int,
        embedder: TextEmbedder,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        top_k: int = DEFAULT_TOP_K,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        client: AsyncQdrantClient | None = None,
    ) -> None:
        # `client` é injetável para testes (ex.: `AsyncQdrantClient(location=":memory:")`)
        # — em produção (`app.main`) sempre None, e o client real é construído
        # a partir de host/port/timeout_s.
        self._client = (
            client
            if client is not None
            else AsyncQdrantClient(host=host, port=port, timeout=int(timeout_s))
        )
        self._embedder = embedder
        self._collection_name = collection_name
        self._top_k = top_k
        self._score_threshold = score_threshold

    async def ensure_collection(self) -> None:
        """Cria a collection se ainda não existir (idempotente)."""
        try:
            exists = await self._client.collection_exists(self._collection_name)
            if not exists:
                dimension = await self._embedder.get_dimension()
                await self._client.create_collection(
                    collection_name=self._collection_name,
                    vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def drop_collection(self) -> None:
        """Remove a collection — usado por scripts/testes para limpeza, não
        acionado no fluxo normal do orchestrator."""
        try:
            await self._client.delete_collection(self._collection_name)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def upsert_chunks(self, chunks: list[str], source: str, domain: str) -> int:
        """Embeda e grava `chunks` na collection, com payload `source`/`domain`.

        # MVP: sem deduplicação nem re-ingestão incremental — reingerir a
        # mesma fonte duas vezes cria pontos duplicados na collection (ver
        # docs/ARCHITECTURE.md §5, linha "RAG — textos, PDFs, BD e sites").
        Retorna o número de pontos gravados.
        """
        if not chunks:
            return 0

        await self.ensure_collection()
        vectors = await self._embedder.embed(chunks)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={"content": chunk, "source": source, "domain": domain},
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        try:
            await self._client.upsert(collection_name=self._collection_name, points=points)
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
        return len(points)

    async def search(self, query: str, domain: str) -> list[Document]:
        """Busca por similaridade na collection de texto, filtrada por `domain`.

        Lista vazia é devolvida tanto quando a collection ainda não existe
        (nada foi ingerido) quanto quando a busca roda normalmente e não
        acha nada acima do limiar — os dois são sinal de negócio válido.
        Falha de infraestrutura (Qdrant fora do ar) vira `RAGConnectionError`
        e propaga, sem ser confundida com busca vazia (ver
        `app.router.rag_client.RAGConnectionError`).
        """
        try:
            exists = await self._client.collection_exists(self._collection_name)
            if not exists:
                return []

            [query_vector] = await self._embedder.embed([query])
            response = await self._client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="domain", match=MatchValue(value=domain))]
                ),
                limit=self._top_k,
                score_threshold=self._score_threshold,
            )
            # Payload ausente/malformado (ex.: ponto gravado por uma versão
            # antiga do script de ingestão, ou edição manual no Qdrant) é
            # tratado como a mesma falha de infraestrutura — não deve
            # propagar como KeyError bruto, que o orchestrator não sabe
            # distinguir de busca vazia (ver docstring da classe).
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
