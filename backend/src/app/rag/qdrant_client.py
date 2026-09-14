"""Cliente RAG real via Qdrant (R4) — ingestão e busca vetorial de texto/PDF.

O contrato (`RAGClient` Protocol, `Document`, `RAGConnectionError`) foi
definido em `app.router.rag_client` já na Fase 1 (ver
docs/superpowers/specs/2026-09-05-roteador-basico-design.md §2.3), para que
o orchestrator fosse testável antes do RAG real existir. Esta classe é a
implementação concreta (ingestão + busca), no módulo `app/rag/` conforme a
estrutura de pastas de docs/CONVENTIONS.md.
"""

import asyncio
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
        # MVP: guarda em memória, confiável só dentro deste processo (um
        # único worker Uvicorn, ver docs/CONVENTIONS.md) — evita repetir
        # `collection_exists` (round trip ao Qdrant) em toda ingestão/busca
        # depois da primeira confirmação. `_collection_lock` evita que duas
        # chamadas concorrentes (ex.: duas ingestões quase simultâneas antes
        # da collection existir) tentem criar a mesma collection ao mesmo
        # tempo (race check-then-act entre `collection_exists` e
        # `create_collection`).
        self._collection_ready = False
        self._collection_lock = asyncio.Lock()

    @property
    def embedding_model_name(self) -> str:
        return self._embedder.model_name

    async def ensure_collection(self) -> None:
        """Cria a collection se ainda não existir (idempotente)."""
        if self._collection_ready:
            return
        try:
            async with self._collection_lock:
                if self._collection_ready:  # outra chamada pode ter criado enquanto esperava
                    return
                exists = await self._client.collection_exists(self._collection_name)
                if not exists:
                    dimension = await self._embedder.get_dimension()
                    await self._client.create_collection(
                        collection_name=self._collection_name,
                        vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
                    )
                self._collection_ready = True
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def drop_collection(self) -> None:
        """Remove a collection — usado por scripts/testes para limpeza, não
        acionado no fluxo normal do orchestrator."""
        try:
            await self._client.delete_collection(self._collection_name)
            self._collection_ready = False
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc

    async def upsert_chunks(
        self, chunks: list[str], source: str, domain: str, document_id: str
    ) -> int:
        """Embeda e grava `chunks` na collection, com payload
        `source`/`domain`/`document_id`.

        `document_id` amarra os pontos gravados ao registro em
        `app.rag.registry` — é o que permite excluir só os pontos de um
        documento específico (ver `delete_by_document_id`), mesmo quando o
        mesmo `source`/`domain` foi ingerido mais de uma vez (sem
        deduplicação — ver docstring do módulo).

        # MVP: sem deduplicação nem re-ingestão incremental — reingerir a
        # mesma fonte duas vezes cria pontos duplicados na collection (ver
        # docs/ARCHITECTURE.md §5, linha "RAG — textos, PDFs, BD e sites").
        Retorna o número de pontos gravados.
        """
        if not chunks:
            return 0

        await self.ensure_collection()
        try:
            # `embed()` (chamada ao modelo de embeddings) precisa estar
            # dentro do mesmo try que o upsert — antes ficava fora e uma
            # falha ali (ex.: erro do modelo com texto extraído de PDF)
            # subia crua em vez de virar `RAGConnectionError`, que é o que
            # `api/rag.py`/`api/chat.py` sabem tratar.
            vectors = await self._embedder.embed(chunks)
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
            if not self._collection_ready:
                exists = await self._client.collection_exists(self._collection_name)
                if not exists:
                    return []
                self._collection_ready = True

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

    async def delete_by_document_id(self, document_id: str) -> None:
        """Remove todos os pontos com aquele `document_id` no payload.

        A exclusão da linha correspondente no registro (Postgres) é feita
        separadamente por quem chama este método (ver `app.api.rag`) — as
        duas exclusões não são transacionais entre si (mesma decisão de
        `upsert_chunks`, ver docs/superpowers/specs/2026-09-14-registro-
        documentos-rag-design.md §3).
        """
        try:
            if not self._collection_ready:
                exists = await self._client.collection_exists(self._collection_name)
                if not exists:
                    return
                self._collection_ready = True

            await self._client.delete(
                collection_name=self._collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
            )
        except Exception as exc:
            raise RAGConnectionError(str(exc)) from exc
