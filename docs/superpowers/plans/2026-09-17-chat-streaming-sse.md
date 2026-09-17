# Streaming (SSE) da resposta do chat — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /api/chat/messages` passa a devolver `text/event-stream`
em vez de JSON síncrono, com um evento `status` avisando quando o modelo
local está carregando (cold-start do Ollama) e eventos `token`
incrementais para a resposta.

**Architecture:** RAG e classificação continuam síncronos (como hoje);
só a chamada final de geração do LLM vira streaming. Um único `POST`
retorna o stream inteiro (sem `GET` separado — ver spec). Eventos SSE
nomeados: `conversation`, `transcription`, `status`, `token`, `done`,
`error`.

**Tech Stack:** FastAPI `StreamingResponse`, Ollama `stream: true`
(`/api/generate`, NDJSON) e `GET /api/ps`, OpenRouter `stream: true`
(SSE OpenAI-compatible) com `stream_options.include_usage`, frontend
`fetch` + `ReadableStream` (sem `EventSource`, que não suporta POST).

**Spec:** `docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md`

## Global Constraints

- RAG e classificação (`classify()`, `rag_client.search()`) permanecem
  chamadas não-streaming, exatamente como hoje — só a geração final muda.
- `is_model_ready()` sempre `True` para `OpenRouterClient` (sem
  conceito de "modelo descarregado" numa API externa).
- Erros que ocorrem **depois** que o stream HTTP já abriu (qualquer coisa
  dentro de `handle_message`) viram evento `error`, nunca mais um HTTP
  4xx/5xx — só erros de validação de entrada (áudio base64 inválido,
  nem `message` nem `audio` presentes) continuam HTTP 400/422 normais,
  porque acontecem antes do stream começar.
- Texto do evento `status` voltado ao cliente final: "Aguarde,
  consultando documentos internos..." — nunca expor "modelo"/"carregar"
  (linguagem técnica) na UI.
- `generate_stream()` usa `timeout=None` na conexão HTTP (mesmo padrão já
  usado por `OllamaClient.pull_model_streaming`) — não hardcode
  `LOCAL_LLM_TIMEOUT_S`/`EXTERNAL_LLM_TIMEOUT_S` nessa chamada.

---

### Task 1: `LLMStreamChunk` e extensão do `LLMClient` Protocol

**Files:**
- Modify: `backend/src/app/router/llm_client.py`

**Interfaces:**
- Produces: `LLMStreamChunk` (Pydantic model), `LLMClient.generate_stream(prompt: str) -> AsyncIterator[LLMStreamChunk]`, `LLMClient.is_model_ready() -> bool` — usados pelas Tasks 2-6.
- Consumes: nada novo (só `pydantic.BaseModel`, `typing.Protocol`).

- [ ] **Step 1: Escrever o arquivo completo**

```python
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
```

- [ ] **Step 2: Rodar a suíte inteira pra confirmar que nada quebrou ainda**

Run (a partir de `backend/`): `.venv/bin/python -m pytest -q`
Expected: mesma contagem de testes de antes, todos passando (essa task só
adiciona tipos, nada os usa ainda — `OllamaClient`/`OpenRouterClient`
continuam implementando só `generate`, o que é compatível em Python
porque `Protocol` não é verificado em runtime sem `@runtime_checkable` +
`isinstance`, que este projeto não usa).

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/router/llm_client.py
git commit -m "feat(chat): adiciona LLMStreamChunk e generate_stream/is_model_ready ao LLMClient Protocol"
```

---

### Task 2: `OllamaClient.is_model_ready()`

**Files:**
- Modify: `backend/src/app/router/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `OllamaClient.is_model_ready() -> bool` — usado pela Task 5.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `backend/tests/test_ollama_client.py`:

```python
async def test_is_model_ready_true_quando_modelo_esta_na_lista_do_ps():
    mock_response = {
        "models": [
            {"name": "outro-modelo:8b"},
            {"name": "llama3.1:8b"},
        ]
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    assert await client.is_model_ready() is True


async def test_is_model_ready_false_quando_modelo_nao_esta_na_lista_do_ps():
    mock_response = {"models": [{"name": "outro-modelo:8b"}]}
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    assert await client.is_model_ready() is False


async def test_is_model_ready_false_quando_lista_vazia():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"models": []})),
    )

    assert await client.is_model_ready() is False
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_ollama_client.py -k is_model_ready -v`
Expected: `FAIL` com `AttributeError: 'OllamaClient' object has no attribute 'is_model_ready'`.

- [ ] **Step 3: Implementar**

Adicionar a `OllamaClient` (logo depois de `list_local_models`, em
`backend/src/app/router/ollama_client.py`):

```python
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
```

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_ollama_client.py -v`
Expected: todos os testes do arquivo passando, incluindo os 3 novos.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "feat(chat): OllamaClient.is_model_ready via GET /api/ps"
```

---

### Task 3: `OllamaClient.generate_stream()`

**Files:**
- Modify: `backend/src/app/router/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Consumes: `LLMStreamChunk` (Task 1), `_mock_streaming_transport` (helper já existente no arquivo de teste, usado por `pull_model_streaming`).
- Produces: `OllamaClient.generate_stream(prompt: str) -> AsyncIterator[LLMStreamChunk]` — usado pela Task 5.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `backend/tests/test_ollama_client.py` (o import de
`LLMStreamChunk` vai no topo do arquivo, junto dos outros imports de
`app.router.ollama_client`/`app.router.llm_client`):

```python
async def test_generate_stream_emite_um_chunk_de_texto_por_linha_e_chunk_final_com_telemetria():
    lines = [
        json.dumps({"response": "Olá"}),
        json.dumps({"response": ", tudo bem?"}),
        json.dumps(
            {
                "response": "",
                "done": True,
                "prompt_eval_count": 12,
                "eval_count": 34,
                "total_duration": 2_500_000_000,
                "load_duration": 500_000_000,
                "prompt_eval_duration": 200_000_000,
                "eval_duration": 1_800_000_000,
            }
        ),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 3
    assert chunks[0] == LLMStreamChunk(text="Olá")
    assert chunks[1] == LLMStreamChunk(text=", tudo bem?")
    assert chunks[2].done is True
    assert chunks[2].text is None
    assert chunks[2].prompt_tokens == 12
    assert chunks[2].completion_tokens == 34
    assert chunks[2].total_duration_ms == 2500.0
    assert chunks[2].load_duration_ms == 500.0
    assert chunks[2].prompt_eval_duration_ms == 200.0
    assert chunks[2].eval_duration_ms == 1800.0
    assert chunks[2].model_name == "llama3.1:8b"


async def test_generate_stream_com_resposta_de_uma_linha_so():
    lines = [
        json.dumps(
            {
                "response": "ok",
                "done": True,
                "prompt_eval_count": 1,
                "eval_count": 1,
                "total_duration": 100_000_000,
            }
        ),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    # Uma linha só, mas com `response` não vazio E `done=True` — emite os
    # dois: o fragmento de texto primeiro, depois o chunk final.
    assert len(chunks) == 2
    assert chunks[0] == LLMStreamChunk(text="ok")
    assert chunks[1].done is True
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_ollama_client.py -k generate_stream -v`
Expected: `FAIL` com `AttributeError: 'OllamaClient' object has no attribute 'generate_stream'`.

- [ ] **Step 3: Implementar**

Adicionar a `OllamaClient`, logo depois de `generate` (importar
`LLMStreamChunk` no topo do módulo junto com `LLMResponse`):

```python
    async def generate_stream(self, prompt: str) -> AsyncIterator[LLMStreamChunk]:
        """Mesmo `/api/generate`, mas com `stream: true` — devolve um
        `LLMStreamChunk` por linha NDJSON. `timeout=None`: uma resposta
        longa (ou um cold-start do modelo) pode legitimamente levar mais
        que `LOCAL_LLM_TIMEOUT_S`, que só vale para a chamada não-streaming
        de classificação (ver
        docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md,
        seção Timeouts). Mesmo padrão de `pull_model_streaming`.
        """
        async with self._client.stream(
            "POST",
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": True},
            timeout=None,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                data = json.loads(line)
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
                            data["load_duration"] / _NS_PER_MS
                            if "load_duration" in data
                            else None
                        ),
                        prompt_eval_duration_ms=(
                            data["prompt_eval_duration"] / _NS_PER_MS
                            if "prompt_eval_duration" in data
                            else None
                        ),
                        eval_duration_ms=(
                            data["eval_duration"] / _NS_PER_MS
                            if "eval_duration" in data
                            else None
                        ),
                        estimated_cost_usd=0.0,
                        model_name=self._model,
                    )
```

Import necessário no topo do arquivo: trocar
`from app.router.llm_client import LLMResponse` por
`from app.router.llm_client import LLMResponse, LLMStreamChunk`.

- [ ] **Step 4: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_ollama_client.py -v`
Expected: todos passando, incluindo os 2 novos.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "feat(chat): OllamaClient.generate_stream via /api/generate stream=true"
```

---

### Task 4: `OpenRouterClient.is_model_ready()` e `generate_stream()`

**Files:**
- Modify: `backend/src/app/router/openrouter_client.py`
- Test: `backend/tests/test_openrouter_client.py`

**Interfaces:**
- Consumes: `LLMStreamChunk` (Task 1).
- Produces: `OpenRouterClient.is_model_ready()` (sempre `True`),
  `OpenRouterClient.generate_stream(prompt: str) -> AsyncIterator[LLMStreamChunk]`
  — usados pela Task 5.

- [ ] **Step 1: Ler o arquivo de teste existente pra confirmar o padrão de mock usado (`httpx.MockTransport`) antes de escrever os novos**

Run: verifique `backend/tests/test_openrouter_client.py` (leia o arquivo
inteiro) — o padrão de mock lá é o mesmo `httpx.MockTransport` de
`test_ollama_client.py`, adaptado ao formato de resposta do OpenRouter
(`choices[0]["message"]["content"]`, `usage`).

- [ ] **Step 2: Escrever os testes que falham**

Adicionar ao final de `backend/tests/test_openrouter_client.py`:

```python
async def test_is_model_ready_sempre_true():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
    )

    assert await client.is_model_ready() is True


def _mock_sse_transport(lines: list[str], status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n\n".join(lines).encode() + b"\n\n"
        return httpx.Response(
            status_code, content=body, headers={"content-type": "text/event-stream"}
        )

    return httpx.MockTransport(handler)


async def test_generate_stream_emite_delta_de_conteudo_e_chunk_final_com_usage():
    lines = [
        'data: {"choices":[{"delta":{"content":"Olá"}}]}',
        'data: {"choices":[{"delta":{"content":", tudo bem?"}}]}',
        'data: {"choices":[{"delta":{}}],"usage":{"prompt_tokens":12,"completion_tokens":34}}',
        "data: [DONE]",
    ]
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        price_per_1k_input_tokens=1.0,
        price_per_1k_output_tokens=2.0,
        client=httpx.AsyncClient(transport=_mock_sse_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 3
    assert chunks[0] == LLMStreamChunk(text="Olá")
    assert chunks[1] == LLMStreamChunk(text=", tudo bem?")
    assert chunks[2].done is True
    assert chunks[2].prompt_tokens == 12
    assert chunks[2].completion_tokens == 34
    # custo: 12/1000*1.0 + 34/1000*2.0 = 0.012 + 0.068 = 0.08
    assert chunks[2].estimated_cost_usd == pytest.approx(0.08)
    assert chunks[2].model_name == "anthropic/claude-3.5-haiku"


async def test_generate_stream_sintetiza_chunk_final_se_provedor_nunca_manda_usage():
    # Provedor agregado pelo OpenRouter que ignora `stream_options.include_usage`
    # — o stream termina em [DONE] sem nenhum chunk trazer `usage`.
    lines = [
        'data: {"choices":[{"delta":{"content":"oi"}}]}',
        "data: [DONE]",
    ]
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="chave-fake",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_sse_transport(lines)),
    )

    chunks = [chunk async for chunk in client.generate_stream("oi")]

    assert len(chunks) == 2
    assert chunks[0] == LLMStreamChunk(text="oi")
    assert chunks[1].done is True
    assert chunks[1].prompt_tokens is None
    assert chunks[1].completion_tokens is None
    assert chunks[1].model_name == "anthropic/claude-3.5-haiku"
```

- [ ] **Step 3: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_openrouter_client.py -k "is_model_ready or generate_stream" -v`
Expected: `FAIL` (`AttributeError`).

- [ ] **Step 4: Implementar**

Reescrever `backend/src/app/router/openrouter_client.py` por completo:

```python
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
```

- [ ] **Step 5: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_openrouter_client.py -v`
Expected: todos passando (os já existentes + os novos).

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/router/openrouter_client.py backend/tests/test_openrouter_client.py
git commit -m "feat(chat): OpenRouterClient.generate_stream e is_model_ready"
```

---

### Task 5: `orchestrator.handle_message` vira async generator

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `LLMClient.generate_stream`/`is_model_ready` (Tasks 2-4).
- Produces: `StatusEvent`, `TokenEvent` (novos, em `orchestrator.py`),
  `RouterDecision` (já existe, agora é o último item emitido em vez do
  valor de retorno) — `handle_message` agora é
  `AsyncIterator[StatusEvent | TokenEvent | RouterDecision]`. Usado pela
  Task 6.

Este é o task mais delicado do plano — mexe na função central do
roteador. Leia `backend/src/app/router/orchestrator.py` e
`backend/tests/test_orchestrator.py` por completo antes de começar.

- [ ] **Step 1: Reescrever os fakes de teste no topo de `test_orchestrator.py`**

Trocar a classe `_FakeLLMClient` existente (e o import de `LLMResponse`)
por (nomes de fixture/helpers como `_resposta_local`/`_resposta_externa`
continuam existindo, sem mudar assinatura):

```python
from app.router.llm_client import LLMResponse, LLMStreamChunk


class _FakeLLMClient:
    def __init__(
        self,
        response: LLMResponse | None = None,
        exception: Exception | None = None,
        model_ready: bool = True,
    ) -> None:
        self._response = response
        self._exception = exception
        self._model_ready = model_ready
        self.calls = 0
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        self.last_prompt = prompt
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response

    async def is_model_ready(self) -> bool:
        return self._model_ready

    async def generate_stream(self, prompt: str):
        self.calls += 1
        self.last_prompt = prompt
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        if self._response.text:
            yield LLMStreamChunk(text=self._response.text)
        yield LLMStreamChunk(
            done=True,
            prompt_tokens=self._response.prompt_tokens,
            completion_tokens=self._response.completion_tokens,
            total_duration_ms=self._response.total_duration_ms,
            load_duration_ms=self._response.load_duration_ms,
            prompt_eval_duration_ms=self._response.prompt_eval_duration_ms,
            eval_duration_ms=self._response.eval_duration_ms,
            estimated_cost_usd=self._response.estimated_cost_usd,
            model_name=self._response.model_name,
        )
```

`_FakeRAGClient` não muda. Adicionar um helper no topo do arquivo (usado
por quase todo teste, pra não repetir o `async for`/coleta em cada um):

```python
async def _coletar_eventos(message, **kwargs):
    return [evento async for evento in handle_message(message, **kwargs)]
```

- [ ] **Step 2: Adaptar CADA teste existente pra usar `_coletar_eventos` e checar o último evento (que é o `RouterDecision`, equivalente ao `decisao` de antes)**

Padrão de adaptação (repita para todos os `async def test_...` do
arquivo que hoje fazem `decisao = await handle_message(...)`):

```python
# antes:
#   decisao = await handle_message(
#       "quero agendar uma visita", recent_messages=[], local_client=local_client,
#       external_client=external_client, rag_client=rag_client, complexity_strategy="heuristic",
#   )
#   assert decisao.domain == "agendamento"

# depois:
eventos = await _coletar_eventos(
    "quero agendar uma visita",
    recent_messages=[],
    local_client=local_client,
    external_client=external_client,
    rag_client=rag_client,
    complexity_strategy="heuristic",
)
decisao = eventos[-1]
assert isinstance(decisao, RouterDecision)
assert decisao.domain == "agendamento"
```

Para os testes que hoje usam `with pytest.raises(...)` em torno de
`await handle_message(...)` (ex.:
`test_rag_indisponivel_propaga_erro_sem_fallback_para_externo`,
`test_ollama_indisponivel_nao_faz_fallback_para_externo`,
`test_falha_do_local_na_classificacao_llm_nao_faz_fallback_para_externo`,
`test_openrouter_indisponivel_propaga_erro`), o padrão vira:

```python
with pytest.raises(RAGConnectionError):  # ou o erro específico do teste
    await _coletar_eventos(
        "...", recent_messages=[], local_client=local_client,
        external_client=external_client, rag_client=rag_client,
        complexity_strategy="heuristic",
    )
```

(`pytest.raises` funciona igual em torno de uma corrotina que itera um
generator até ele levantar — a exceção propaga normalmente.)

Para `test_documento_recuperado_pelo_rag_e_injetado_no_prompt_do_llm` e
similares que inspecionam `local_client.last_prompt`, nada muda (o fake
ainda grava `last_prompt` em `generate_stream`, igual fazia em
`generate`).

Para `test_log_de_decisao_tem_campos_json_de_primeiro_nivel`, ajustar
para coletar os eventos e checar o log depois (o log estruturado
`router_decision` continua sendo emitido uma vez só, no fim, igual hoje).

- [ ] **Step 3: Adicionar um teste novo pro evento `status`**

```python
async def test_modelo_local_nao_carregado_emite_status_antes_dos_tokens():
    local_client = _FakeLLMClient(response=_resposta_local(), model_ready=False)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert isinstance(eventos[0], StatusEvent)
    assert eventos[0].status == "carregando_modelo"


async def test_modelo_local_ja_carregado_nao_emite_status():
    local_client = _FakeLLMClient(response=_resposta_local(), model_ready=True)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert not any(isinstance(e, StatusEvent) for e in eventos)


async def test_tokens_emitidos_em_ordem_e_resposta_final_e_a_concatenacao():
    local_client = _FakeLLMClient(
        response=LLMResponse(text="Boa tarde!", total_duration_ms=50.0)
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    eventos = await _coletar_eventos(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    tokens = [e for e in eventos if isinstance(e, TokenEvent)]
    assert len(tokens) == 1
    assert tokens[0].text == "Boa tarde!"
    assert eventos[-1].resposta == "Boa tarde!"
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py -v`
Expected: falhas generalizadas (`handle_message` ainda devolve
`RouterDecision` direto, não é um generator — `async for`/`[... async
for ...]` sobre o retorno de uma corrotina normal levanta `TypeError`).

- [ ] **Step 5: Implementar — reescrever `orchestrator.py`**

Adicionar as duas classes de evento (logo depois da classe
`RouterDecision` já existente):

```python
class StatusEvent(BaseModel):
    status: str


class TokenEvent(BaseModel):
    text: str
```

Trocar a assinatura e o corpo de `handle_message` — a parte de
classificação e RAG **não muda nada** (mesmo código, `raise` continua
`raise`, propaga normalmente de dentro de um generator). Só a parte
final (do comentário `client = local_client if ...` até o final da
função) muda:

```python
from collections.abc import AsyncIterator

# ... (resto do arquivo até a parte final de handle_message igual a hoje) ...

async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision]:
    # ... (classificação e RAG, idênticos ao código atual, sem nenhuma mudança) ...

    prompt = _build_prompt(message, documentos) if documentos else message

    client = local_client if backend_escolhido == "local" else external_client

    if not await client.is_model_ready():
        yield StatusEvent(status="carregando_modelo")

    texto_partes: list[str] = []
    chunk_final: LLMStreamChunk | None = None
    try:
        async for chunk in client.generate_stream(prompt):
            if chunk.text:
                texto_partes.append(chunk.text)
                yield TokenEvent(text=chunk.text)
            if chunk.done:
                chunk_final = chunk
    except Exception as exc:
        logger.error(
            "backend_indisponivel",
            extra={
                "router": {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": classification.domain,
                    "etapa": "geracao",
                    "erro": str(exc),
                }
            },
        )
        if backend_escolhido == "local":
            raise LocalBackendIndisponivelError(str(exc)) from exc
        raise ExternalBackendIndisponivelError(str(exc)) from exc

    assert chunk_final is not None, "generate_stream deve sempre terminar com um chunk done=True"

    # TPS usa `eval_duration` (tempo de geração pura) — `total_duration`
    # inclui também `load_duration` (carregar o modelo) e
    # `prompt_eval_duration` (processar o prompt), então usar o total
    # subestimaria a taxa de geração de tokens.
    tps: float | None = None
    if chunk_final.completion_tokens and chunk_final.eval_duration_ms:
        gen_duration_s = max(chunk_final.eval_duration_ms / 1000.0, 0.001)
        tps = round(chunk_final.completion_tokens / gen_duration_s, 2)

    resposta_completa = "".join(texto_partes)

    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=backend_escolhido,
        motivo_escalonamento=motivo,
        resposta=resposta_completa,
        latencia_ms=chunk_final.total_duration_ms or 0.0,
        tokens_entrada=chunk_final.prompt_tokens,
        tokens_saida=chunk_final.completion_tokens,
        custo_estimado_usd=chunk_final.estimated_cost_usd,
        modelo_usado=chunk_final.model_name or getattr(client, "model", None),
        ttft_ms=chunk_final.prompt_eval_duration_ms,
        tps=tps,
        rag_retrieval_ms=rag_retrieval_ms,
        rag_chunks_count=rag_chunks_count,
        rag_avg_score=rag_avg_score,
    )
    logger.info(
        "router_decision",
        extra={"router": {"event": "router_decision", **decisao.model_dump()}},
    )
    yield decisao
```

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_orchestrator.py -v`
Expected: todos os testes (adaptados + novos) passando.

- [ ] **Step 7: Rodar a suíte inteira do backend**

Run: `.venv/bin/python -m pytest -q` (a partir de `backend/`)
Expected: só `tests/test_chat_api.py` deve estar quebrado agora (Task 6
conserta) — todo o resto deve continuar verde.

- [ ] **Step 8: Commit**

```bash
git add backend/src/app/router/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(chat): handle_message vira async generator (status/token/RouterDecision)"
```

---

### Task 6: `api/chat.py` devolve `StreamingResponse`

**Files:**
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/src/app/models/chat.py`
- Test: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `StatusEvent`/`TokenEvent`/`RouterDecision` (Task 5).
- Produces: contrato SSE final de `POST /api/chat/messages` — consumido
  pela Task 7 (frontend).

- [ ] **Step 1: Trocar `ChatMessageResponse` em `models/chat.py` pelos modelos por evento**

Em `backend/src/app/models/chat.py`, remover a classe `ChatMessageResponse`
inteira e adicionar no lugar (mantendo `ChatMessageRequest` sem nenhuma
mudança):

```python
class ChatDoneEventData(BaseModel):
    """Payload do evento `done` do stream SSE (telemetria completa da
    resposta) — ver docs/FRONTEND.md §4 e
    docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md."""

    domain: str = Field(..., description="Domínio identificado pelo roteador (R3, R7).")
    backend_used: str = Field(..., description='"local" ou "externo".')
    escalation_reason: str = Field(
        ..., description='"nenhum", "fora_escopo", "rag_vazio" ou "complexidade_alta".'
    )
    model_name: str | None = Field(default=None, description="Nome do modelo de LLM que gerou a resposta.")
    prompt_tokens: int | None = Field(default=None, description="Quantidade de tokens de entrada (prompt).")
    completion_tokens: int | None = Field(default=None, description="Quantidade de tokens de saída (resposta).")
    latency_ms: float | None = Field(default=None, description="Tempo total de latência da resposta em ms.")
    ttft_ms: float | None = Field(default=None, description="Tempo do primeiro token (Time To First Token) em ms.")
    tps: float | None = Field(default=None, description="Taxa de geração de tokens por segundo (Tokens/s).")
    confidence: float | None = Field(default=None, description="Confiança na classificação do roteador.")
    complexity: str | None = Field(default=None, description="Complexidade estimada da mensagem.")
    estimated_cost_usd: float | None = Field(default=None, description="Custo estimado da requisição em USD.")
    rag_retrieval_ms: float | None = Field(default=None, description="Tempo de busca vetorial no RAG em ms.")
    rag_chunks_count: int | None = Field(default=None, description="Quantidade de chunks recuperados do RAG.")
    rag_avg_score: float | None = Field(default=None, description="Score médio de similaridade dos chunks do RAG.")
```

- [ ] **Step 2: Reescrever os fakes no topo de `test_chat_api.py`**

`_FakeLLMClient` ganha os mesmos 3 métodos do Task 5 (`generate`,
`is_model_ready`, `generate_stream`) — copiar exatamente a mesma
implementação usada em `test_orchestrator.py` (mesmo padrão, evita
divergência entre os dois arquivos de teste).

- [ ] **Step 3: Reescrever os testes existentes pra ler o stream SSE**

Adicionar um helper no topo do arquivo:

```python
def _parse_sse(body: str) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in body.split("\n\n"):
        if not bloco.strip():
            continue
        tipo = None
        dados = None
        for linha in bloco.split("\n"):
            if linha.startswith("event:"):
                tipo = linha[len("event:") :].strip()
            elif linha.startswith("data:"):
                dados = json.loads(linha[len("data:") :].strip())
        if tipo and dados is not None:
            eventos.append((tipo, dados))
    return eventos
```

Cada teste existente que hoje faz `response = client.post(...)` e depois
`assert response.json()["campo"] == valor` passa a fazer:

```python
response = client.post("/api/chat/messages", json={"message": "..."})
assert response.status_code == 200
eventos = _parse_sse(response.text)
tipos = [tipo for tipo, _ in eventos]
assert tipos[0] == "conversation"
assert tipos[-1] == "done"
dados_done = dict(eventos)["done"] if len(dict(eventos)) == len(eventos) else next(d for t, d in eventos if t == "done")
assert dados_done["domain"] == "vendas"
```

(Nota: `dict(eventos)` só funciona se cada tipo aparecer uma vez —
`token` pode aparecer várias vezes, então use sempre
`next(d for t, d in eventos if t == "...")` ou
`[d for t, d in eventos if t == "token"]` para tipos que podem repetir.)

Testes de erro (ex. `RAGConnectionError`, `LocalBackendIndisponivelError`)
adaptam de "`assert response.status_code == 503`" para: status ainda é
200 (o stream já abriu), e o último evento é `error`:

```python
eventos = _parse_sse(response.text)
assert eventos[-1][0] == "error"
assert "temporariamente indisponível" in eventos[-1][1]["detail"]
```

Testes de erro de validação de entrada ANTES do stream (áudio base64
inválido, nem message nem audio) **não mudam** — continuam
`response.status_code == 400`/`422` normal, sem SSE (acontecem antes do
`StreamingResponse` ser criado).

- [ ] **Step 4: Rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_chat_api.py -v`
Expected: falhas (o endpoint ainda devolve `ChatMessageResponse`, que
não existe mais em `models/chat.py`).

- [ ] **Step 5: Implementar — reescrever `api/chat.py`**

```python
"""Endpoint HTTP do chat (R2, R3, R5) — encaminha para o orchestrator do roteador."""

import base64
import binascii
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatDoneEventData, ChatMessageRequest
from app.router.llm_client import LLMClient
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.rag_client import RAGClient, RAGConnectionError
from app.stt.whisper_client import SttClient, SttIndisponivelError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_HISTORY_MESSAGES = 3

# MVP: histórico de conversa mantido em memória por processo (dict simples
# `conversation_id -> últimas mensagens`) — sem persistência em banco nem
# resumo automático, que ficam para a Fase 6 (R9, ver docs/ROADMAP.md). O
# histórico também não sobrevive a um restart do processo.
_conversation_history: dict[str, list[str]] = {}


def reset_conversation_history() -> None:
    """Limpa o histórico em memória — usado pelos testes para isolar casos."""
    _conversation_history.clear()


def get_local_client(request: Request) -> LLMClient:
    return request.app.state.local_client


def get_external_client(request: Request) -> LLMClient:
    return request.app.state.external_client


def get_rag_client(request: Request) -> RAGClient:
    return request.app.state.rag_client


def get_complexity_strategy(request: Request) -> str:
    return request.app.state.complexity_strategy


def get_stt_client(request: Request) -> SttClient:
    return request.app.state.stt_client


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/messages")
async def send_message(
    payload: ChatMessageRequest,
    local_client: LLMClient = Depends(get_local_client),
    external_client: LLMClient = Depends(get_external_client),
    rag_client: RAGClient = Depends(get_rag_client),
    complexity_strategy: str = Depends(get_complexity_strategy),
    stt_client: SttClient = Depends(get_stt_client),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid4())

    # MVP: quando `payload.audio` vem preenchido, o texto transcrito
    # substitui `payload.message` como mensagem efetiva enviada ao
    # orchestrator — ver docstring anterior deste arquivo (git blame) para
    # o raciocínio completo, inalterado por esta mudança.
    effective_message = payload.message
    transcribed_message: str | None = None
    if payload.audio:
        try:
            audio_bytes = base64.b64decode(payload.audio, validate=True)
        except binascii.Error as exc:
            raise HTTPException(
                status_code=400, detail="Campo 'audio' não é base64 válido."
            ) from exc

        try:
            transcribed = await stt_client.transcribe(audio_bytes)
        except SttIndisponivelError as exc:
            logger.error(
                "stt_indisponivel",
                extra={"router": {"event": "stt_indisponivel", "erro": str(exc)}},
            )
            raise HTTPException(
                status_code=503, detail="Serviço de transcrição de áudio indisponível."
            ) from exc

        if transcribed:
            effective_message = transcribed
            transcribed_message = transcribed

    if not effective_message:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível entender o áudio. Tente novamente ou digite sua mensagem.",
        )

    recent_messages = list(_conversation_history.get(conversation_id, []))

    async def event_stream():
        yield _sse("conversation", {"conversation_id": conversation_id})
        if transcribed_message is not None:
            yield _sse("transcription", {"transcribed_message": transcribed_message})

        try:
            async for event in handle_message(
                message=effective_message,
                recent_messages=recent_messages,
                local_client=local_client,
                external_client=external_client,
                rag_client=rag_client,
                complexity_strategy=complexity_strategy,
            ):
                if isinstance(event, StatusEvent):
                    yield _sse("status", {"status": event.status})
                elif isinstance(event, TokenEvent):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, RouterDecision):
                    history = _conversation_history.setdefault(conversation_id, [])
                    history.append(effective_message)
                    del history[:-_MAX_HISTORY_MESSAGES]
                    done_data = ChatDoneEventData(
                        domain=event.domain,
                        backend_used=event.backend_escolhido,
                        escalation_reason=event.motivo_escalonamento,
                        model_name=event.modelo_usado,
                        prompt_tokens=event.tokens_entrada,
                        completion_tokens=event.tokens_saida,
                        latency_ms=event.latencia_ms,
                        ttft_ms=event.ttft_ms,
                        tps=event.tps,
                        confidence=event.confidence,
                        complexity=event.complexity,
                        estimated_cost_usd=event.custo_estimado_usd,
                        rag_retrieval_ms=event.rag_retrieval_ms,
                        rag_chunks_count=event.rag_chunks_count,
                        rag_avg_score=event.rag_avg_score,
                    )
                    yield _sse("done", done_data.model_dump())
        except (
            LocalBackendIndisponivelError,
            ExternalBackendIndisponivelError,
            RAGConnectionError,
        ) as exc:
            logger.error(
                "chat_dependencia_indisponivel",
                extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
            )
            yield _sse(
                "error", {"detail": "Serviço temporariamente indisponível, tente novamente."}
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 6: Rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_chat_api.py -v`
Expected: todos passando.

- [ ] **Step 7: Rodar a suíte inteira do backend + lint**

Run (a partir de `backend/`): `.venv/bin/python -m pytest -q && .venv/bin/ruff check src/ tests/ && .venv/bin/ruff format --check src/ tests/`
Expected: tudo verde, sem erros de lint/formatação.

- [ ] **Step 8: Commit**

```bash
git add backend/src/app/api/chat.py backend/src/app/models/chat.py backend/tests/test_chat_api.py
git commit -m "feat(chat): POST /api/chat/messages devolve text/event-stream (SSE)"
```

---

### Task 7: `frontend/lib/api/chat.ts` — cliente SSE

**Files:**
- Modify: `frontend/lib/api/chat.ts`
- Modify: `frontend/lib/types/chat.ts`
- Test: criar `frontend/tests/lib/api/chat.test.ts`

**Interfaces:**
- Consumes: contrato SSE da Task 6.
- Produces: `sendChatMessage(params: SendChatMessageParams): Promise<void>`
  com callbacks — usado pela Task 8.

- [ ] **Step 1: Atualizar `frontend/lib/types/chat.ts`**

Remover `ChatMessageResponse` (não existe mais como resposta única) e
adicionar `ChatDoneEventData` no lugar (mesmos campos, sem
`conversation_id`/`message`/`transcribed_message`, que agora vêm de
eventos separados):

```typescript
export interface ChatDoneEventData {
  domain: ChatDomain;
  backend_used: ChatBackendUsed;
  escalation_reason: ChatEscalationReason;
  model_name?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  latency_ms?: number | null;
  ttft_ms?: number | null;
  tps?: number | null;
  confidence?: number | null;
  complexity?: string | null;
  estimated_cost_usd?: number | null;
  rag_retrieval_ms?: number | null;
  rag_chunks_count?: number | null;
  rag_avg_score?: number | null;
}
```

(`ChatDomain`, `ChatBackendUsed`, `ChatEscalationReason`, `ChatMetrics`,
`ChatMessageRequest`, `ChatUIMessage` continuam exatamente iguais — não
remover.)

- [ ] **Step 2: Escrever o teste que falha**

Criar `frontend/tests/lib/api/chat.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";

import { sendChatMessage } from "@/lib/api/chat";

function sseStream(blocks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < blocks.length) {
        controller.enqueue(encoder.encode(blocks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchOnce(body: ReadableStream<Uint8Array>, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      body,
    } as Response),
  );
}

describe("sendChatMessage", () => {
  it("chama os callbacks na ordem certa pra um fluxo de texto simples", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: token\ndata: {"text":"Olá"}\n\n',
        'event: token\ndata: {"text":", tudo bem?"}\n\n',
        'event: done\ndata: {"domain":"vendas","backend_used":"local","escalation_reason":"nenhum"}\n\n',
      ]),
    );

    const onConversationId = vi.fn();
    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await sendChatMessage({
      message: "oi",
      onConversationId,
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken,
      onDone,
      onError,
    });

    expect(onConversationId).toHaveBeenCalledWith("conv-1");
    expect(onToken).toHaveBeenNthCalledWith(1, "Olá");
    expect(onToken).toHaveBeenNthCalledWith(2, ", tudo bem?");
    expect(onDone).toHaveBeenCalledWith(
      expect.objectContaining({ domain: "vendas", backend_used: "local" }),
    );
    expect(onError).not.toHaveBeenCalled();
  });

  it("chama onStatus quando o evento status chega antes dos tokens", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: status\ndata: {"status":"carregando_modelo"}\n\n',
        'event: token\ndata: {"text":"ok"}\n\n',
        'event: done\ndata: {"domain":"vendas","backend_used":"local","escalation_reason":"nenhum"}\n\n',
      ]),
    );

    const onStatus = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus,
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError: vi.fn(),
    });

    expect(onStatus).toHaveBeenCalledWith("carregando_modelo");
  });

  it("chama onError quando o evento error chega", async () => {
    mockFetchOnce(
      sseStream([
        'event: conversation\ndata: {"conversation_id":"conv-1"}\n\n',
        'event: error\ndata: {"detail":"Serviço temporariamente indisponível, tente novamente."}\n\n',
      ]),
    );

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Serviço temporariamente indisponível, tente novamente.");
  });

  it("chama onError quando o fetch falha (rede)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Não foi possível conectar ao servidor. Verifique sua conexão.");
  });

  it("chama onError quando a resposta HTTP não é 2xx", async () => {
    mockFetchOnce(sseStream([]), false, 503);

    const onError = vi.fn();
    await sendChatMessage({
      message: "oi",
      onConversationId: vi.fn(),
      onTranscription: vi.fn(),
      onStatus: vi.fn(),
      onToken: vi.fn(),
      onDone: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Serviço temporariamente indisponível. Tente novamente.");
  });
});
```

- [ ] **Step 3: Rodar e ver falhar**

Run (a partir de `frontend/`): `npx vitest run tests/lib/api/chat.test.ts`
Expected: falha — `sendChatMessage` ainda tem a assinatura antiga
(retorna `Promise<ChatMessageResponse>`, não aceita callbacks).

- [ ] **Step 4: Implementar — reescrever `frontend/lib/api/chat.ts`**

```typescript
import type { ChatDoneEventData, ChatMessageRequest } from "@/lib/types/chat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com `POST /api/chat/messages` (rede ou HTTP não-2xx). */
export class ChatApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

export interface SendChatMessageParams {
  /** Texto digitado pelo usuário. Opcional se `audioBase64` for informado. */
  message?: string;
  /** Áudio gravado (base64), alternativa ao texto — ver `AudioRecorder`. */
  audioBase64?: string;
  conversationId?: string;
  onConversationId: (id: string) => void;
  onTranscription: (text: string) => void;
  onStatus: (status: string) => void;
  onToken: (text: string) => void;
  onDone: (data: ChatDoneEventData) => void;
  onError: (message: string) => void;
}

/** Extrai `{ event, data }` de um bloco SSE (linhas `event:`/`data:` até uma linha em branco). */
function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const linha of block.split("\n")) {
    if (linha.startsWith("event:")) {
      event = linha.slice("event:".length).trim();
    } else if (linha.startsWith("data:")) {
      data += linha.slice("data:".length).trim();
    }
  }
  return data ? { event, data } : null;
}

/**
 * Envia uma mensagem (texto e/ou áudio) ao backend e entrega a resposta
 * incrementalmente via os callbacks (SSE) — nunca lança, erros de
 * rede/HTTP/stream viram chamada a `onError`.
 *
 * MVP: sem upload de imagem (ver `docs/FRONTEND.md` §3/§4) — apenas texto
 * e/ou áudio.
 */
export async function sendChatMessage({
  message,
  audioBase64,
  conversationId,
  onConversationId,
  onTranscription,
  onStatus,
  onToken,
  onDone,
  onError,
}: SendChatMessageParams): Promise<void> {
  const payload: ChatMessageRequest = {
    message,
    conversation_id: conversationId,
    audio: audioBase64 ?? null,
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    onError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    return;
  }

  if (!response.ok || !response.body) {
    onError(
      response.status === 503
        ? "Serviço temporariamente indisponível. Tente novamente."
        : "Não foi possível enviar sua mensagem. Tente novamente.",
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex = buffer.indexOf("\n\n");
      while (sepIndex !== -1) {
        const block = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const parsed = parseSseBlock(block);
        if (parsed) {
          const json = JSON.parse(parsed.data);
          switch (parsed.event) {
            case "conversation":
              onConversationId(json.conversation_id);
              break;
            case "transcription":
              onTranscription(json.transcribed_message);
              break;
            case "status":
              onStatus(json.status);
              break;
            case "token":
              onToken(json.text);
              break;
            case "done":
              onDone(json as ChatDoneEventData);
              break;
            case "error":
              onError(json.detail ?? "Erro inesperado. Tente novamente.");
              break;
          }
        }
        sepIndex = buffer.indexOf("\n\n");
      }
    }
  } catch {
    onError("Conexão perdida durante o recebimento da resposta. Tente novamente.");
  }
}
```

- [ ] **Step 5: Rodar e ver passar**

Run: `npx vitest run tests/lib/api/chat.test.ts`
Expected: todos os 5 testes passando.

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/api/chat.ts frontend/lib/types/chat.ts frontend/tests/lib/api/chat.test.ts
git commit -m "feat(chat): sendChatMessage consome o stream SSE via callbacks"
```

---

### Task 8: `ChatModal.tsx` consome o stream

**Files:**
- Modify: `frontend/components/chat/ChatModal.tsx`
- Test: `frontend/tests/components/ChatModal.test.tsx`

**Interfaces:**
- Consumes: `sendChatMessage` com callbacks (Task 7).

- [ ] **Step 1: Adaptar os mocks em `ChatModal.test.tsx`**

O mock de `sendChatMessage` (hoje `vi.fn()` que resolve um objeto) passa
a ser uma implementação que invoca os callbacks recebidos, simulando o
stream. Trocar o mock global do módulo por uma implementação customizada,
por teste, que chama os callbacks certos na ordem certa — ex., pro
teste "envia mensagem de texto e exibe a resposta do assistente":

```typescript
mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
  onConversationId("conv-1");
  onToken("Temos esse produto em estoque.");
  onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
});
```

Repetir o padrão pros outros testes existentes (erro com retry, áudio,
fallback de transcrição vazia, retry de áudio) — cada um chama os
callbacks que fazem sentido pro cenário (ex.: o teste de erro chama só
`onError`, o de áudio chama `onTranscription` antes de `onToken`/`onDone`).

Adicionar 2 testes novos:

```typescript
it("mostra o texto de status e substitui pelo primeiro token", async () => {
  mockedSendChatMessage.mockImplementation(
    async ({ onConversationId, onStatus, onToken, onDone }) => {
      onConversationId("conv-1");
      onStatus("carregando_modelo");
      // dá tempo da bolha de status renderizar antes do token chegar
      await Promise.resolve();
      onToken("Resposta real.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    },
  );

  const user = userEvent.setup();
  renderModal();
  await user.type(screen.getByLabelText("Mensagem"), "oi");
  await user.click(screen.getByRole("button", { name: "Enviar" }));

  expect(await screen.findByText("Resposta real.")).toBeInTheDocument();
  expect(screen.queryByText(/consultando documentos internos/)).not.toBeInTheDocument();
});

it("concatena múltiplos tokens na mesma bolha", async () => {
  mockedSendChatMessage.mockImplementation(
    async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Olá");
      onToken(", tudo bem?");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    },
  );

  const user = userEvent.setup();
  renderModal();
  await user.type(screen.getByLabelText("Mensagem"), "oi");
  await user.click(screen.getByRole("button", { name: "Enviar" }));

  expect(await screen.findByText("Olá, tudo bem?")).toBeInTheDocument();
});
```

(`renderModal()` é o helper já existente no arquivo, se não existir
ainda nesse ponto do código real, usar o mesmo padrão de `render(<ChatModal
open onOpenChange={vi.fn()} />)` já usado nos outros testes do arquivo.)

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run tests/components/ChatModal.test.tsx`
Expected: falhas generalizadas (o componente ainda usa `await
sendChatMessage(...)` com o retorno antigo).

- [ ] **Step 3: Implementar — reescrever `submitMessage`/`submitAudio` em `ChatModal.tsx`**

```typescript
  async function submitMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isSending) return;

    addMessage({ id: crypto.randomUUID(), role: "user", text: trimmed });
    setInput("");
    setIsSending(true);
    setError(null);

    const assistantId = crypto.randomUUID();
    let bolhaCriada = false;
    let textoAcumulado = "";

    function garantirBolha(textoInicial: string) {
      if (!bolhaCriada) {
        bolhaCriada = true;
        addMessage({ id: assistantId, role: "assistant", text: textoInicial });
      } else {
        updateMessage(assistantId, { text: textoInicial });
      }
    }

    await sendChatMessage({
      message: trimmed,
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: () => {},
      onStatus: (status) => {
        if (status === "carregando_modelo") {
          garantirBolha("🤖 Aguarde, consultando documentos internos...");
        }
      },
      onToken: (chunk) => {
        textoAcumulado += chunk;
        garantirBolha(textoAcumulado);
      },
      onDone: (data) => {
        if (!bolhaCriada) {
          garantirBolha(textoAcumulado);
        }
        updateMessage(assistantId, {
          domain: data.domain,
          backendUsed: data.backend_used,
          metrics: {
            modelName: data.model_name ?? undefined,
            promptTokens: data.prompt_tokens ?? undefined,
            completionTokens: data.completion_tokens ?? undefined,
            latencyMs: data.latency_ms ?? undefined,
            ttftMs: data.ttft_ms ?? undefined,
            tps: data.tps ?? undefined,
            confidence: data.confidence ?? undefined,
            complexity: data.complexity ?? undefined,
            estimatedCostUsd: data.estimated_cost_usd ?? undefined,
            ragRetrievalMs: data.rag_retrieval_ms ?? undefined,
            ragChunksCount: data.rag_chunks_count ?? undefined,
            ragAvgScore: data.rag_avg_score ?? undefined,
            escalationReason: data.escalation_reason,
          },
        });
      },
      onError: (msg) => {
        setError({ text: msg, retry: { message: trimmed } });
      },
    });

    setIsSending(false);
  }

  async function submitAudio(audioBase64: string) {
    if (isSending) return;

    const pendingId = crypto.randomUUID();
    addMessage({ id: pendingId, role: "user", text: AUDIO_PENDING_TEXT });
    setIsSending(true);
    setError(null);

    const assistantId = crypto.randomUUID();
    let bolhaCriada = false;
    let textoAcumulado = "";
    let transcricaoRecebida = false;

    function garantirBolha(textoInicial: string) {
      if (!bolhaCriada) {
        bolhaCriada = true;
        addMessage({ id: assistantId, role: "assistant", text: textoInicial });
      } else {
        updateMessage(assistantId, { text: textoInicial });
      }
    }

    await sendChatMessage({
      audioBase64,
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: (text) => {
        transcricaoRecebida = true;
        updateMessage(pendingId, { text: text || AUDIO_FALLBACK_TEXT });
      },
      onStatus: (status) => {
        if (status === "carregando_modelo") {
          garantirBolha("🤖 Aguarde, consultando documentos internos...");
        }
      },
      onToken: (chunk) => {
        textoAcumulado += chunk;
        garantirBolha(textoAcumulado);
      },
      onDone: (data) => {
        if (!bolhaCriada) {
          garantirBolha(textoAcumulado);
        }
        updateMessage(assistantId, {
          domain: data.domain,
          backendUsed: data.backend_used,
          metrics: {
            modelName: data.model_name ?? undefined,
            promptTokens: data.prompt_tokens ?? undefined,
            completionTokens: data.completion_tokens ?? undefined,
            latencyMs: data.latency_ms ?? undefined,
            ttftMs: data.ttft_ms ?? undefined,
            tps: data.tps ?? undefined,
            confidence: data.confidence ?? undefined,
            complexity: data.complexity ?? undefined,
            estimatedCostUsd: data.estimated_cost_usd ?? undefined,
            ragRetrievalMs: data.rag_retrieval_ms ?? undefined,
            ragChunksCount: data.rag_chunks_count ?? undefined,
            ragAvgScore: data.rag_avg_score ?? undefined,
            escalationReason: data.escalation_reason,
          },
        });
      },
      onError: (msg) => {
        if (!transcricaoRecebida) {
          updateMessage(pendingId, { text: AUDIO_FAILED_TEXT });
        }
        setError({ text: msg, retry: { audioBase64 } });
      },
    });

    setIsSending(false);
  }
```

`ChatEscalationReason` já é o tipo de `data.escalation_reason` vindo de
`ChatDoneEventData` — não precisa de cast, remover qualquer `??
undefined` que sobrar nesse campo específico (o de cima já assume
presente, igual o schema documenta).

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run tests/components/ChatModal.test.tsx`
Expected: todos os testes (adaptados + 2 novos) passando.

- [ ] **Step 5: Rodar a suíte inteira do frontend + typecheck + lint**

Run (a partir de `frontend/`): `npm test -- --run && npx tsc --noEmit && npm run lint`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/components/chat/ChatModal.tsx frontend/tests/components/ChatModal.test.tsx
git commit -m "feat(chat): ChatModal consome o stream SSE (status/token/done)"
```

---

### Task 9: Documentação

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`
- Modify: `docs/FRONTEND.md`

**Interfaces:**
- Consumes: nada (task de documentação, roda depois de tudo implementado).

- [ ] **Step 1: `docs/ARCHITECTURE.md`**

Adicionar uma "Decisão registrada" (mesmo padrão das outras já
existentes em §5), logo antes de "### Tabela de escopo por requisito":

```markdown
**Decisão registrada (Fase 8/R2-R3, 2026-09-17):** `POST
/api/chat/messages` passa a devolver `text/event-stream` (SSE) em vez de
JSON síncrono — um único POST (não o desenho de dois endpoints,
`GET /api/chat/stream/{conversation_id}`, do rascunho original em
`docs/FRONTEND.md`, que exigiria manter a geração rodando em background
independente de alguém ouvir, buffer para replay e limpeza de gerações
órfãs — engenharia especulativa que este protótipo de sessão única por
aba não precisa). Eventos nomeados: `conversation`, `transcription`,
`status` (só quando o backend local não está com o modelo carregado na
VRAM — `GET /api/ps` do Ollama, cold-start leva ~15-17s), `token`
(fragmento de texto), `done` (telemetria completa), `error`. Detalhes:
`docs/superpowers/specs/2026-09-17-chat-streaming-sse-design.md`. `# MVP:
o desenho de dois endpoints (reconexão, múltiplos ouvintes) fica
registrado como evolução futura, não implementar sem necessidade
concreta`.
```

- [ ] **Step 2: `docs/ROADMAP.md`**

Trocar o item de Fase 8 (hoje `[~]`) sobre streaming:

```markdown
- [x] Implementar envio de texto e exibição do streaming de resposta (SSE) —
      `POST /api/chat/messages` devolve `text/event-stream`
      (`app/api/chat.py`), com evento `status` avisando cold-start do
      modelo local (`OllamaClient.is_model_ready`, `GET /api/ps`) antes de
      gerar — decisão registrada em `docs/ARCHITECTURE.md` §5
```

- [ ] **Step 3: `docs/FRONTEND.md`**

Na tabela de endpoints (§4), trocar a linha de
`GET /api/chat/stream/{conversation_id}` (removê-la — não existe mais,
era o desenho antigo) e atualizar a descrição de
`POST /api/chat/messages` pra "Envia mensagem (texto e/ou áudio);
resposta é `text/event-stream` (SSE)". Substituir o bloco de exemplo
JSON (contrato atual, com `// Response (200)` de JSON síncrono) pela
descrição dos 6 eventos SSE (mesmo conteúdo já escrito na spec, seção
"Contrato do endpoint" — copiar de lá, adaptando "escolhida"/"proposto"
para o tempo verbal de fato implementado).

- [ ] **Step 4: Commit**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md docs/FRONTEND.md
git commit -m "docs: contrato de streaming (SSE) do chat documentado"
```
