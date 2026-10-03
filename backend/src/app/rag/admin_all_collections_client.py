"""Adapter `RAGClient` (mesmo Protocol de `ActiveCollectionRagClient`) usado
só quando o chat confirma, via `app.api.auth.verificar_admin_por_token`, que
quem está conversando é o Admin (decisão de 2026-09-30, a pedido explícito
do desenvolvedor, `docs/ARCHITECTURE.md` §6): em vez de restringir à
collection `chat` ativa, busca nela **e** em toda collection
`purpose="mcp_b2b"` **e** `purpose="admin"` — o Admin acessa todo o
conteúdo do RAG (principal + específico do canal B2B + exclusivo dele),
nunca o contrário (visitante comum nunca vê `mcp_b2b`/`admin`, ver
`ActiveCollectionRagClient`).
"""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.rag.collections_registry import list_collections
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.multi_collection_search import buscar_em_varias_collections
from app.rag.qdrant_client import QdrantRAGClient
from app.router.rag_client import Document, RAGConnectionError


class AdminAllCollectionsRagClient:
    def __init__(
        self,
        qdrant: QdrantRAGClient,
        session_factory: async_sessionmaker,
        embedders: EmbedderRegistry,
    ) -> None:
        self._qdrant = qdrant
        self._session_factory = session_factory
        self._embedders = embedders

    async def search(
        self,
        query: str,
        domain: str,
        top_k: int = 3,
        score_threshold: float = 0.35,
    ) -> list[Document]:
        try:
            async with self._session_factory() as session:
                collections = await list_collections(session)
        except SQLAlchemyError as exc:
            raise RAGConnectionError(str(exc)) from exc

        alvo = [
            c
            for c in collections
            if c.is_active and c.purpose in ("chat", "mcp_b2b", "admin")
        ]
        pares = await buscar_em_varias_collections(
            alvo,
            self._qdrant,
            self._embedders,
            query,
            domain,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return [documento for _, documento in pares]
