"""Schemas Pydantic das características de modelo (multimodalidade,
contexto, specs) — ver docs/superpowers/specs/2026-10-03-caracteristicas-
modelo-hover-design.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModelSource = Literal["openrouter", "ollama", "huggingface"]


class ModelCharacteristicsResponse(BaseModel):
    source: ModelSource
    tag: str
    is_multimodal: bool
    input_modalities: list[str]
    output_modalities: list[str]
    context_length: int | None
    parameter_size: str | None
    quantization: str | None
    pricing_prompt_per_1k: float | None
    pricing_completion_per_1k: float | None
    knowledge_cutoff: str | None
    fetched_at: datetime


class CharacteristicsRefreshRequest(BaseModel):
    source: ModelSource
    tag: str = Field(..., min_length=1)
