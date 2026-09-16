"""Dependências FastAPI compartilhadas entre os módulos de API do RAG
(documentos, collections, playground) — extraídas para não duplicar a mesma
leitura de `app.state` em três arquivos.
"""

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient


def get_qdrant_client(request: Request) -> QdrantRAGClient:
    return request.app.state.qdrant_client


def get_embedder_registry(request: Request) -> EmbedderRegistry:
    return request.app.state.embedder_registry


def get_uploads_dir(request: Request) -> Path:
    return request.app.state.rag_uploads_dir


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.db_sessionmaker() as session:
        yield session
