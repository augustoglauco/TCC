"""Modelos SQLAlchemy do backend (primeiro uso real do Postgres — ver
docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md).
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RagDocument(Base):
    """Registro de um documento ingerido no RAG (R4, além do MVP).

    `id` também é gravado como campo de payload em cada ponto do Qdrant
    daquele documento (ver `app.rag.qdrant_client.upsert_chunks`) — é o que
    permite excluir um documento e seus vetores juntos.
    """

    __tablename__ = "rag_documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    filename: Mapped[str]
    domain: Mapped[str]
    chunk_count: Mapped[int]
    embedding_model: Mapped[str]
    chunk_size: Mapped[int]
    chunk_overlap: Mapped[int]
    origin: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
