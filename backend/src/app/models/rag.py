"""Schemas Pydantic do endpoint de ingestão de documentos do RAG (R4).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/rag/documents`).
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# MVP: só os três domínios com RAG de texto (o mesmo conjunto usado por
# `app.rag.qdrant_client` para filtrar busca) — "agendamento" e "fora_escopo"
# não têm collection própria (ver `app.router.classifier.Domain`).
RagDomain = Literal["vendas", "suporte", "atendimento"]


class DocumentIngestResponse(BaseModel):
    """Resposta de `POST /api/rag/documents`."""

    filename: str = Field(..., description="Nome do arquivo enviado.")
    domain: RagDomain = Field(..., description="Domínio informado no upload.")
    chunks: int = Field(..., description="Número de chunks gravados no Qdrant.")


class DocumentRegistryResponse(BaseModel):
    """Um item de `GET /api/rag/documents` — espelha `app.db.models.RagDocument`."""

    id: UUID
    filename: str = Field(..., description="Nome do arquivo ingerido.")
    domain: RagDomain
    chunk_count: int = Field(..., description="Número de chunks gravados no Qdrant.")
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    origin: Literal["upload", "batch_script"]
    created_at: datetime

    model_config = {"from_attributes": True}
