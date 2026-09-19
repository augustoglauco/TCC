"""Schemas Pydantic dos endpoints do crawler de páginas do RAG (R4, Fase 2)
— ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.models.rag import RagDomain


class CrawlRunRequest(BaseModel):
    """Corpo de `POST /api/rag/crawler/run`. `max_pages` ausente usa o
    default configurado (`crawler_max_pages_default`, runtime settings) —
    sem teto rígido no backend (spec §2, decisão explícita)."""

    url: HttpUrl
    depth: int = Field(..., ge=0)
    max_pages: int | None = Field(default=None, ge=1)


class CrawlRunResponse(BaseModel):
    pages_visited: int
    auto_ingested: list[str]
    queued: list[str]
    errors: list[str]


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
