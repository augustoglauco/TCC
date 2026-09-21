"""Schemas Pydantic dos endpoints do crawler de páginas do RAG (R4, Fase 2)
— ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.rag import RagDomain


class PendingPageResponse(BaseModel):
    id: UUID
    url: str
    text_snippet: str
    domain_proposed: RagDomain
    confidence: float
    created_at: datetime


class ApprovePendingPageRequest(BaseModel):
    domain: RagDomain


class ApprovedPageResponse(BaseModel):
    url: str
    domain: RagDomain
    chunks: int
