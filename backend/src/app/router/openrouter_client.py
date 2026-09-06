import time

import httpx

from app.router.llm_client import LLMResponse


class OpenRouterClient:
    """Cliente para o backend externo via OpenRouter (docs/TECHNOLOGY_STACK.md).

    Diferente do Ollama, a API do OpenRouter não devolve breakdown de
    load/eval duration — total_duration_ms é medido no lado do cliente,
    conforme a metodologia de docs/EVALUATION.md #3.
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

        cost = 0.0
        if prompt_tokens:
            cost += (prompt_tokens / 1000) * self._price_in
        if completion_tokens:
            cost += (completion_tokens / 1000) * self._price_out

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
            eval_duration_ms=None,
            estimated_cost_usd=cost,
        )
