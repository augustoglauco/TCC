"""Schemas Pydantic do endpoint de ingestão de documentos do RAG (R4).

Contrato espelhado em `docs/FRONTEND.md` §4 (`POST /api/rag/documents`).
"""

from typing import Literal

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
