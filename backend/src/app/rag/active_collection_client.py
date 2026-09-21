"""Adapter que implementa o Protocol `RAGClient` (usado pelo orchestrator)
resolvendo, a cada busca, qual collection está marcada como ativa — ver
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §4.1.

Isso é uma coupling nova: a busca do RAG passa a depender do Postgres (antes
só a ingestão dependia, desde a Entrega A). `# MVP: sem cache do id da
collection ativa em memória — um round trip extra ao Postgres por mensagem
de chat é aceitável neste protótipo`.
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.rag.collections_registry import get_active_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError


class ActiveCollectionRagClient:
    def __init__(
        self,
        qdrant: QdrantRAGClient,
        session_factory: async_sessionmaker,
        embedders: EmbedderRegistry,
    ) -> None:
        self._qdrant = qdrant
        self._session_factory = session_factory
        self._embedders = embedders

    async def search(self, query: str, domain: str) -> list[Document]:
        try:
            async with self._session_factory() as session:
                collection = await get_active_collection(session)
        except SQLAlchemyError as exc:
            raise RAGConnectionError(str(exc)) from exc
        if collection is None:
            return []
        # Defesa em profundidade: a collection ativa nunca deveria ser
        # `mcp_b2b` (a ativação dessas é bloqueada em
        # `activate_collection`), mas falhamos fechado se a invariante for
        # quebrada no futuro — conteúdo restrito ao MCP B2B jamais é servido
        # ao chat público (ver
        # docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §4).
        if collection.purpose == "mcp_b2b":
            return []
        embedder = self._embedders.get(collection.embedding_model)
        return await self._qdrant.search(collection.name, embedder, query, domain)
