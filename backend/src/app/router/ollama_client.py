import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.router.llm_client import LLMResponse

_NS_PER_MS = 1_000_000


@dataclass(frozen=True)
class LocalModel:
    """Um modelo já baixado localmente no Ollama (`GET /api/tags`)."""

    name: str
    size_bytes: int
    modified_at: str


@dataclass(frozen=True)
class PullProgressLine:
    """Uma linha do stream NDJSON de `POST /api/pull` — ver
    docs/superpowers/specs/2026-09-16-local-model-manager-design.md §2."""

    status: str
    digest: str | None
    total: int | None
    completed: int | None
    error: str | None


class OllamaClient:
    """Cliente para o backend local via Ollama (docs/TECHNOLOGY_STACK.md).

    Além de `generate` (geração de chat), expõe `list_local_models`/
    `pull_model_streaming` para o gerenciador administrativo de modelos
    locais (além do MVP — ver
    docs/superpowers/specs/2026-09-16-local-model-manager-design.md).
    `model` é mutável (property) para permitir trocar qual modelo o chat
    usa em runtime, sem recriar a instância — o `# MVP: escolha manual de
    teste, não a de produção, sem persistir entre restarts` está registrado
    em `app.main`, não aqui.
    """

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

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

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
            prompt_eval_duration_ms=(
                data["prompt_eval_duration"] / _NS_PER_MS
                if "prompt_eval_duration" in data
                else None
            ),
            eval_duration_ms=(
                data["eval_duration"] / _NS_PER_MS if "eval_duration" in data else None
            ),
            estimated_cost_usd=0.0,
            model_name=self._model,
        )

    async def list_local_models(self) -> list[LocalModel]:
        """Modelos já baixados localmente (`GET /api/tags`)."""
        response = await self._client.get(f"{self._base_url}/api/tags", timeout=self._timeout_s)
        response.raise_for_status()
        data = response.json()
        return [
            LocalModel(name=item["name"], size_bytes=item["size"], modified_at=item["modified_at"])
            for item in data.get("models", [])
        ]

    async def is_model_ready(self) -> bool:
        """Checa se `self._model` já está carregado na memória do Ollama
        (`GET /api/ps` — modelos rodando agora, diferente de `/api/tags`
        que lista todos os já baixados). Usado para decidir se emite o
        evento `status` de "carregando" antes de uma geração que vai
        pagar o custo de cold-start (ver
        docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md).
        """
        response = await self._client.get(f"{self._base_url}/api/ps", timeout=self._timeout_s)
        response.raise_for_status()
        data = response.json()
        return any(item.get("name") == self._model for item in data.get("models", []))

    async def pull_model_streaming(self, name: str) -> AsyncIterator[PullProgressLine]:
        """Baixa `name` (biblioteca do Ollama ou `hf.co/usuario/repo[:tag]`
        do Hugging Face), gerando uma `PullProgressLine` por linha do stream
        NDJSON de `POST /api/pull`.

        # MVP: sem timeout — downloads de modelos grandes podem levar
        # minutos; quem chama este método roda numa tarefa em background,
        # nunca segurando a requisição HTTP que a disparou (ver
        # `app.api.local_models`).
        """
        async with self._client.stream(
            "POST",
            f"{self._base_url}/api/pull",
            json={"model": name, "stream": True},
            timeout=None,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                yield PullProgressLine(
                    status=data.get("status", ""),
                    digest=data.get("digest"),
                    total=data.get("total"),
                    completed=data.get("completed"),
                    error=data.get("error"),
                )
