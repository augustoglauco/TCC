from typing import Protocol

from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_duration_ms: float
    load_duration_ms: float | None = None
    eval_duration_ms: float | None = None
    estimated_cost_usd: float = 0.0


class LLMClient(Protocol):
    async def generate(self, prompt: str) -> LLMResponse: ...
