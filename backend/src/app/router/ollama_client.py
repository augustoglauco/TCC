import httpx

from app.router.llm_client import LLMResponse

_NS_PER_MS = 1_000_000


class OllamaClient:
    """Cliente para o backend local via Ollama (docs/TECHNOLOGY_STACK.md)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._client = client or httpx.AsyncClient()

    async def generate(self, prompt: str) -> LLMResponse:
        response = await self._client.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=self._timeout_s,
        )
        response.raise_for_status()
        data = response.json()
        return LLMResponse(
            text=data["response"],
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            total_duration_ms=data.get("total_duration", 0) / _NS_PER_MS,
            load_duration_ms=(
                data["load_duration"] / _NS_PER_MS if "load_duration" in data else None
            ),
            eval_duration_ms=(
                data["eval_duration"] / _NS_PER_MS if "eval_duration" in data else None
            ),
            estimated_cost_usd=0.0,
        )
