import base64
import json
import time
from collections.abc import AsyncIterator

import httpx

from app.ocr.image_processor import detect_image_format
from app.router.llm_client import LLMResponse, LLMStreamChunk


class VisionModelIndisponivelError(Exception):
    """Modelo de visão externo não configurado ou falhou — o motor de
    identificação de imagem trata como 'não identificado' (sem fallback)."""


_VALID_DOMAINS = {"vendas", "suporte", "atendimento", "agendamento", "fora_escopo"}

_DOMAIN_CRITERIA = {
    "vendas": "Interesse em comprar, orçamento, preço ou catálogo de produtos.",
    "suporte": "Produto com defeito, erro ou problema técnico já adquirido.",
    "atendimento": "Nota fiscal, troca, devolução, cancelamento ou reclamação.",
    "agendamento": "Quer marcar, remarcar ou confirmar uma visita/horário.",
    "fora_escopo": "Não se encaixa claramente em nenhuma opção acima.",
}


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
        vision_model: str = "",
        jev_model: str = "",
        jev_timeout_s: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_s = timeout_s
        self._price_in = price_per_1k_input_tokens
        self._price_out = price_per_1k_output_tokens
        self._client = client or httpx.AsyncClient()
        # Modelo multimodal usado só no fluxo de identificação de imagem
        # (R6, Fase 3) — separado do modelo de texto (`_model`), ajustável em
        # runtime. Vazio = fallback externo de visão desligado.
        self._vision_model = vision_model
        # Modelo do classificador estruturado TypeSafe Jev (R3, Fase 1,
        # além do MVP — ver docs/ARCHITECTURE.md §5).
        # MVP: nome do modelo só configurável via env/restart (JEV_MODEL_NAME),
        # diferente de `vision_model` acima, que é editável em runtime pelo
        # admin — não há caso de uso que justifique trocar o modelo do Jev
        # sem redeploy. Vazio = provedor "jev_openrouter" no admin fica sem
        # efeito prático (classify_intent_jev levanta erro, capturado pelo
        # fallback gracioso do classificador).
        self._jev_model = jev_model
        # Orçamento de timeout PRÓPRIO do Jev (achado da revisão final):
        # compartilhar `timeout_s`/`external_llm_timeout_s` (30s default, do
        # LLM de chat) faria uma chamada travada ao Jev — um modelo "System
        # One" anunciado como rápido, sub-segundo — custar até 30s ao
        # visitante antes do fallback gracioso disparar. Não editável em
        # runtime pelo admin (mesmo padrão de `jev_model`, só `JEV_TIMEOUT_S`
        # via env/restart).
        self._jev_timeout_s = jev_timeout_s

    @property
    def timeout_s(self) -> float:
        return self._timeout_s

    @timeout_s.setter
    def timeout_s(self, value: float) -> None:
        self._timeout_s = value

    @property
    def vision_model(self) -> str:
        return self._vision_model

    @vision_model.setter
    def vision_model(self, value: str) -> None:
        self._vision_model = value

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

    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        """Envia uma imagem + prompt a um modelo de visão e devolve o texto cru.

        Usado pelo motor de identificação de produto (R6, Fase 3). A imagem
        vai como data URI base64 no formato multimodal OpenAI-compatible
        (`image_url`). Levanta `VisionModelIndisponivelError` se o modelo de
        visão não estiver configurado ou a chamada falhar — o chamador trata
        isso como "não identificado", sem escalar erro ao usuário.

        # MVP: sem streaming (resposta curta e estruturada) e sem cálculo de
        # custo (o benchmark de custo da Fase 10 é sobre o modelo de texto).
        """
        if not self._vision_model:
            raise VisionModelIndisponivelError("EXTERNAL_VISION_MODEL_NAME não configurado.")

        fmt = detect_image_format(image_bytes)
        if fmt is None:
            raise VisionModelIndisponivelError("Formato de imagem não reconhecido.")
        mime = f"image/{fmt.lower()}"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._vision_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": data_uri}},
                            ],
                        }
                    ],
                },
                timeout=self._timeout_s,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise VisionModelIndisponivelError(str(exc)) from exc

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
                # MVP: `choices` pode vir PRESENTE mas VAZIO (ex.: o chunk de
                # `usage` com `stream_options.include_usage=true` costuma vir
                # como `{"choices": [], "usage": {...}}`) — `.get("choices",
                # [{}])` só cobre a chave ausente, não a lista vazia, então
                # `or [{}]` é necessário para não estourar IndexError.
                choices = data.get("choices") or [{}]
                delta = choices[0].get("delta") or {}
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

    async def classify_intent_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[str, float]:
        """Classifica o domínio via TypeSafe Jev, endpoint dedicado do
        OpenRouter (`/systemone`, não `/chat/completions`) — o modelo devolve
        uma decisão tipada (`answers.dominio.choice`/`.confidence`), sem
        geração de texto livre nem parsing de JSON solto.
        """
        if not self._jev_model:
            raise ValueError("jev_model não configurado (JEV_MODEL_NAME).")

        contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
        response = await self._client.post(
            f"{self._base_url}/systemone",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._jev_model,
                "state": f"Contexto prévio:\n{contexto}\n\nMensagem: {message}",
                "questions": {
                    "dominio": {
                        "type": "choice",
                        "instructions": (
                            "Classifique a mensagem do cliente em um dos domínios de atendimento."
                        ),
                        "criteria": _DOMAIN_CRITERIA,
                    }
                },
            },
            timeout=self._jev_timeout_s,
        )
        response.raise_for_status()
        answer = response.json()["answers"]["dominio"]
        choice = str(answer.get("choice", "fora_escopo")).lower().strip()
        confidence = float(answer.get("confidence", 0.5))
        if choice not in _VALID_DOMAINS:
            choice = "fora_escopo"
        return choice, confidence
