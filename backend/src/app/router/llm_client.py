from collections.abc import AsyncIterator
from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_duration_ms: float
    load_duration_ms: float | None = None
    # Tempo de processar o prompt antes de começar a gerar tokens — proxy de
    # "time to first token" (TTFT) disponível em requisição não-streaming
    # (não confundir com `load_duration_ms`, que é o tempo de carregar o
    # modelo na memória/VRAM, ~0 após o primeiro uso — métrica diferente).
    prompt_eval_duration_ms: float | None = None
    eval_duration_ms: float | None = None
    estimated_cost_usd: float = 0.0
    model_name: str | None = None


class LLMStreamChunk(BaseModel):
    """Um fragmento do stream de `generate_stream`.

    Fragmentos intermediários vêm só com `text` preenchido. O último chunk
    do stream tem `done=True`, `text=None`, e os campos de telemetria
    preenchidos (mesmo significado de `LLMResponse`, sem duplicar `text`
    porque o texto completo já foi entregue nos chunks anteriores).
    """

    text: str | None = None
    done: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_duration_ms: float | None = None
    load_duration_ms: float | None = None
    prompt_eval_duration_ms: float | None = None
    eval_duration_ms: float | None = None
    estimated_cost_usd: float = 0.0
    model_name: str | None = None


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> LLMResponse: ...

    def generate_stream(self, prompt: str) -> AsyncIterator[LLMStreamChunk]: ...

    async def is_model_ready(self) -> bool: ...
