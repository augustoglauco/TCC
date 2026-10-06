import base64
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from app.router.llm_client import LLMResponse, LLMStreamChunk, VisionModelIndisponivelError

_NS_PER_MS = 1_000_000


class LocalVisionResult(str):
    """Subclasse de str que preserva o texto retornado por
    `OllamaClient.describe_image` e carrega telemetria de tokens — espelha
    `VisionResult` (`app.router.openrouter_client`), mas sem custo (modelo
    local, mesma instância já residente em VRAM usada para texto)."""

    content: str
    prompt_tokens: int | None
    completion_tokens: int | None
    model_name: str | None

    def __new__(
        cls,
        content: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        model_name: str | None = None,
    ):
        obj = super().__new__(cls, content)
        obj.content = content
        obj.prompt_tokens = prompt_tokens
        obj.completion_tokens = completion_tokens
        obj.cost_prompt_usd = 0.0
        obj.cost_completion_usd = 0.0
        obj.estimated_cost_usd = 0.0
        obj.model_name = model_name
        return obj


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
    """Cliente para o backend local via Ollama (docs/ARCHITECTURE.md §2).

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
        temperature: float | None = None,
        num_ctx: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        repeat_penalty: float | None = None,
        seed: int | None = None,
        keep_alive: str | int | None = "-1",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_s = timeout_s
        self._temperature = temperature
        self._num_ctx = num_ctx
        self._top_p = top_p
        self._top_k = top_k
        self._repeat_penalty = repeat_penalty
        self._seed = seed
        self._keep_alive = keep_alive
        self._client = client or httpx.AsyncClient()

    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        self._model = value

    @property
    def keep_alive(self) -> str | int | None:
        return self._keep_alive

    @keep_alive.setter
    def keep_alive(self, value: str | int | None) -> None:
        self._keep_alive = value

    @property
    def timeout_s(self) -> float:
        return self._timeout_s

    @timeout_s.setter
    def timeout_s(self, value: float) -> None:
        self._timeout_s = value

    @property
    def temperature(self) -> float | None:
        return self._temperature

    @temperature.setter
    def temperature(self, value: float | None) -> None:
        self._temperature = value

    @property
    def num_ctx(self) -> int | None:
        return self._num_ctx

    @num_ctx.setter
    def num_ctx(self, value: int | None) -> None:
        self._num_ctx = value

    @property
    def top_p(self) -> float | None:
        return self._top_p

    @top_p.setter
    def top_p(self, value: float | None) -> None:
        self._top_p = value

    @property
    def top_k(self) -> int | None:
        return self._top_k

    @top_k.setter
    def top_k(self, value: int | None) -> None:
        self._top_k = value

    @property
    def repeat_penalty(self) -> float | None:
        return self._repeat_penalty

    @repeat_penalty.setter
    def repeat_penalty(self, value: float | None) -> None:
        self._repeat_penalty = value

    @property
    def seed(self) -> int | None:
        return self._seed

    @seed.setter
    def seed(self, value: int | None) -> None:
        self._seed = value

    def _normalize_keep_alive(self, value: str | int | None) -> Any:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError, TypeError:
            return value

    def _build_payload(self, prompt: str, stream: bool, think: bool | None = None) -> dict:
        payload: dict = {"model": self._model, "prompt": prompt, "stream": stream}
        if self._keep_alive is not None:
            payload["keep_alive"] = self._normalize_keep_alive(self._keep_alive)
        options: dict = {}
        if self._temperature is not None:
            options["temperature"] = self._temperature
        if self._num_ctx is not None:
            options["num_ctx"] = self._num_ctx
        if self._top_p is not None:
            options["top_p"] = self._top_p
        if self._top_k is not None:
            options["top_k"] = self._top_k
        if self._repeat_penalty is not None:
            options["repeat_penalty"] = self._repeat_penalty
        if self._seed is not None:
            options["seed"] = self._seed
        if options:
            payload["options"] = options
        if think is not None:
            payload["think"] = think
        return payload

    async def preload(self) -> dict | None:
        """Carrega o modelo na memória/VRAM com o keep_alive configurado (elimina cold-start)."""
        payload = {
            "model": self._model,
            "keep_alive": self._normalize_keep_alive(self._keep_alive),
        }
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    async def unload(self) -> dict | None:
        """Descarrega o modelo da VRAM imediatamente (keep_alive: 0)."""
        payload = {"model": self._model, "keep_alive": 0}
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    async def get_loaded_status(self) -> dict | None:
        """Consulta GET /api/ps para verificar se o modelo ativo está carregado na VRAM."""
        try:
            resp = await self._client.get(f"{self._base_url}/api/ps", timeout=5.0)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                for m in models:
                    if m.get("name") == self._model or m.get("model") == self._model:
                        return m
            return None
        except Exception:
            return None

    async def generate(self, prompt: str) -> LLMResponse:
        # think=False: os três chamadores de generate() (classify_with_llm,
        # extract_booking_slots, crawler_classifier) só querem um JSON curto
        # — sem geração em streaming, então "pensamento" do modelo (achado
        # real: 2684 tokens de raciocínio para uma resposta de ~30 tokens,
        # ~50s, às vezes resposta vazia/errada) nunca aparece pro usuário e
        # só atrasa/arrisca estourar o timeout. generate_stream() (resposta
        # de chat de verdade) não muda — lá o "pensamento" pode ajudar a
        # qualidade e o usuário já vê tokens chegando (TTFT não é afetado do
        # mesmo jeito). Ollama ignora "think" para modelos sem essa
        # capability (ver `ollama show <modelo>`), então isso não quebra
        # nada em modelos que não pensam.
        response = await self._client.post(
            f"{self._base_url}/api/generate",
            json=self._build_payload(prompt, stream=False, think=False),
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
            cost_prompt_usd=0.0,
            cost_completion_usd=0.0,
            estimated_cost_usd=0.0,
            model_name=self._model,
        )

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        """Envia uma imagem + prompt ao modelo local (Ollama) e devolve o
        texto cru — visão LOCAL, tentada antes do fallback para visão
        externa (decisão registrada em docs/ARCHITECTURE.md §4, 2026-10-06).
        Reaproveita `self._model` (a mesma instância já residente em VRAM
        usada para texto), sem baixar nem carregar modelo adicional.

        Levanta `VisionModelIndisponivelError` se `self._model` não tiver
        capability `vision` (checado via `GET/POST /api/show`, já que
        mandar `images` para um modelo sem suporte não falha explicitamente
        — ou ignora a imagem, ou responde algo não confiável) ou se a
        chamada falhar — o chamador trata como "indisponível" e cai para o
        próximo nível do fallback, igual a `OpenRouterClient.describe_image`.
        """
        details = await self.get_model_details(self._model)
        capabilities = (details or {}).get("capabilities") or []
        if "vision" not in capabilities:
            raise VisionModelIndisponivelError(
                f"Modelo local '{self._model}' não tem capability de visão."
            )

        payload = self._build_payload(prompt, stream=False, think=False)
        payload["images"] = [base64.b64encode(image_bytes).decode("ascii")]
        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout_s,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise VisionModelIndisponivelError(str(exc)) from exc

        data = response.json()
        texto = data.get("response", "")
        if not texto.strip():
            raise VisionModelIndisponivelError(
                f"Modelo local '{self._model}' não retornou conteúdo para a imagem."
            )
        return LocalVisionResult(
            content=texto,
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            model_name=self._model,
        )

    async def generate_stream(self, prompt: str) -> AsyncIterator[LLMStreamChunk]:
        """Mesmo `/api/generate`, mas com `stream: true` — devolve um
        `LLMStreamChunk` por linha NDJSON. `timeout=None`: uma resposta
        longa (ou um cold-start do modelo) pode legitimamente levar mais
        que `LOCAL_LLM_TIMEOUT_S`, que só vale para a chamada não-streaming
        de classificação (ver
        docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md,
        seção Timeouts). Mesmo padrão de `pull_model_streaming`.

        think=False: correção de 2026-09-24 (docs/ARCHITECTURE.md §5) — a
        decisão original de `think: false` só em `generate()` supunha que
        "pensar" nunca prejudica o chat via streaming. Achado real,
        reproduzido direto contra `POST /api/generate`: um modelo com
        capability `thinking` (`qwen3.5:9b`) pode gastar TODO o orçamento de
        geração (`num_predict`/janela de contexto) só na fase de raciocínio
        — o payload chega em `done: true` com `response` vazio em 100% das
        linhas e `eval_count` não-zero, sem nunca emitir texto de resposta.
        Como o `response` real (quando existe) sempre vem em linhas
        separadas do campo `thinking`, ignorar `thinking` (como este método
        já fazia) não bastava — o problema é o orçamento consumido antes de
        chegar no `response`, não o parsing.
        """
        async with self._client.stream(
            "POST",
            f"{self._base_url}/api/generate",
            json=self._build_payload(prompt, stream=True, think=False),
            timeout=None,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get("error"):
                    # O Ollama pode emitir uma linha `{"error": "..."}` no meio
                    # do stream (ex.: falta de VRAM durante o cold-start do
                    # modelo) em vez de `response`/`done` — sem isso, o stream
                    # terminava em silêncio, sem nunca emitir um chunk final.
                    # Propaga como exceção normal para o orchestrator converter
                    # em `LocalBackendIndisponivelError`.
                    raise RuntimeError(data["error"])
                texto = data.get("response") or ""
                if texto:
                    yield LLMStreamChunk(text=texto)
                if data.get("done"):
                    yield LLMStreamChunk(
                        done=True,
                        prompt_tokens=data.get("prompt_eval_count"),
                        completion_tokens=data.get("eval_count"),
                        total_duration_ms=(
                            data["total_duration"] / _NS_PER_MS
                            if "total_duration" in data
                            else None
                        ),
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
                        cost_prompt_usd=0.0,
                        cost_completion_usd=0.0,
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

    async def get_model_details(self, name: str) -> dict | None:
        """Detalhes completos de um modelo já baixado (`POST /api/show`) —
        usado pelo cache de características de modelo (além do MVP, ver
        docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-
        design.md). `None` em qualquer falha (modelo não baixado, rede
        indisponível, etc.) — característica de modelo é best-effort, nunca
        deve quebrar a tela administrativa.
        """
        try:
            response = await self._client.post(
                f"{self._base_url}/api/show",
                json={"name": name},
                timeout=self._timeout_s,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError, ValueError:
            return None
