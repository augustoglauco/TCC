import json
import time
from collections.abc import AsyncIterator

import httpx

from app.router.llm_client import LLMResponse, LLMStreamChunk


class OpenRouterClient:
    """Cliente para o backend externo via OpenRouter (docs/TECHNOLOGY_STACK.md).

    Diferente do Ollama, a API do OpenRouter não devolve breakdown de
    load/eval duration — total_duration_ms é medido no lado do cliente,
    conforme a metodologia de docs/EVALUATION.md #3. `is_model_ready`
    sempre devolve `True` — não existe conceito de "modelo descarregado"
    numa API externa (ver
    docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_s: float,
        price_per_1k_input_tokens: float = 0.0,
        price_per_1k_output_tokens: float = 0.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._price_in = price_per_1k_input_tokens
        self._price_out = price_per_1k_output_tokens
        self._client = client or httpx.AsyncClient()

    async def is_model_ready(self) -> bool:
        return True

    def _custo(self, prompt_tokens: int | None, completion_tokens: int | None) -> float:
        cost = 0.0
        if prompt_tokens:
            cost += (prompt_tokens / 1000) * self._price_in
        if completion_tokens:
            cost += (completion_tokens / 1000) * self._price_out
        return cost

    async def generate(self, prompt: str) -> LLMResponse:
        started_at = time.monotonic()
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model, "messages": [{"role": "user", "content": prompt}]},
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        elapsed_ms = (time.monotonic() - started_at) * 1000
        data = response.json()
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")

        # MVP: assume o formato bem-formado da resposta do OpenRouter — sem
        # checagem defensiva contra `choices` vazio/ausente (um payload
        # malformado vira KeyError/IndexError, tratado pelo orchestrator como
        # falha do backend externo).
        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_duration_ms=elapsed_ms,
            load_duration_ms=None,
            prompt_eval_duration_ms=None,
            eval_duration_ms=None,
            estimated_cost_usd=self._custo(prompt_tokens, completion_tokens),
            model_name=self._model,
        )

    async def generate_stream(self, prompt: str) -> AsyncIterator[LLMStreamChunk]:
        """`stream: true` no formato OpenAI-compatible — a resposta já vem
        em SSE (`data: {...}\\n\\n`, terminando em `data: [DONE]\\n\\n`).
        `stream_options.include_usage` faz o penúltimo chunk (antes de
        `[DONE]`) trazer `usage` com a contagem de tokens, usada pro chunk
        final (`done=True`) com custo estimado.

        # MVP: o OpenRouter agrega vários provedores — nem todos respeitam
        # `include_usage` de forma consistente. Se o stream terminar sem
        # nenhum chunk trazer `usage`, sintetiza um chunk final "vazio"
        # (só com `total_duration_ms` medido no cliente) em vez de nunca
        # emitir `done=True` — o orchestrator depende de sempre receber um
        # chunk final para fechar a resposta.
        """
        started_at = time.monotonic()
        chunk_final_emitido = False
        async with self._client.stream(
            "POST",
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
                "stream_options": {"include_usage": True},
            },
            timeout=None,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[len("data:") :].strip()
                if raw == "[DONE]":
                    break
                data = json.loads(raw)
                delta = data.get("choices", [{}])[0].get("delta", {})
                texto = delta.get("content") or ""
                if texto:
                    yield LLMStreamChunk(text=texto)
                usage = data.get("usage")
                if usage:
                    elapsed_ms = (time.monotonic() - started_at) * 1000
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    chunk_final_emitido = True
                    yield LLMStreamChunk(
                        done=True,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_duration_ms=elapsed_ms,
                        estimated_cost_usd=self._custo(prompt_tokens, completion_tokens),
                        model_name=self._model,
                    )

        if not chunk_final_emitido:
            yield LLMStreamChunk(
                done=True,
                total_duration_ms=(time.monotonic() - started_at) * 1000,
                model_name=self._model,
            )
