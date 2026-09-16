"""Schemas Pydantic do gerenciador de modelos locais (Ollama, além do
MVP) — ver docs/superpowers/specs/2026-09-16-local-model-manager-design.md.
"""

from typing import Literal

from pydantic import BaseModel, Field


class LocalModelResponse(BaseModel):
    name: str
    size_bytes: int
    modified_at: str
    is_active: bool


class LocalModelsListResponse(BaseModel):
    models: list[LocalModelResponse]
    active_model: str


class ActivateModelRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PullModelRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PullStatusResponse(BaseModel):
    status: Literal["pulling", "done", "error"]
    percent: float | None = None
    detail: str | None = None
