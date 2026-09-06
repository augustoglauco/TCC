# Roteador Básico (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o roteador/orquestrador básico do backend — cliente de LLM local (Ollama) e externo (OpenRouter), classificador de intenção (domínio + complexidade) e a lógica de decisão local/externo/RAG, com log estruturado — cobrindo R1/R3 da Fase 1 do `docs/ROADMAP.md`.

**Architecture:** Três contratos (`LLMClient`, `RAGClient`, `ClassificationResult`) desacoplam o `orchestrator.py` das implementações concretas. `OllamaClient` e `OpenRouterClient` implementam `LLMClient`; `NullRAGClient` é um stub de `RAGClient` até a Fase 2 trazer o Qdrant real. O `orchestrator.py` nunca faz fallback silencioso entre backends em caso de falha de infraestrutura — falha de infra é erro duro, não sinal de roteamento.

**Tech Stack:** Python 3.11+, `httpx` (async, já em `pyproject.toml`), `pydantic` v2, `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`, já configurado). Nenhuma dependência nova é necessária.

**Spec:** `docs/superpowers/specs/2026-09-05-roteador-basico-design.md`

## Global Constraints

- Python 3.11+, type hints em todo código novo (`docs/CONVENTIONS.md`).
- Chamadas de I/O (LLM, RAG) são `async` (`docs/CONVENTIONS.md`).
- Nunca hardcode chaves de API — `OPENROUTER_API_KEY` só via `.env`/`.env.example` com placeholder (`docs/CONVENTIONS.md`, regra 4 do `CLAUDE.md`).
- Simplificações de MVP marcadas com comentário `# MVP: <limitação>` no código (regra 2 do `CLAUDE.md`).
- `ruff check` + `ruff format` antes de cada commit.
- Falha de infraestrutura (Ollama ou RAG indisponível) nunca faz fallback silencioso para outro backend — é erro duro que propaga (spec, Seção 2.4).
- Nenhuma tarefa deste plano depende de GPU real ou de um Ollama/OpenRouter rodando de verdade — todos os testes usam `httpx.MockTransport` ou fakes locais.
- Fora do escopo deste plano (ver spec, Seção 6): implementação real do `RAGClient` (Qdrant), endpoint HTTP/composition root que instancia os clientes a partir de `Settings`, MCP Google Calendar, persistência de `router_logs` em banco, escolha final de `OPENROUTER_MODEL`, scripts de avaliação comparativa em `eval/`.

---

## Task 1: Configuração do roteador (`config.py`, `.env.example`)

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/.env.example`
- Modify: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.router_complexity_strategy: str` (default `"heuristic"`), `Settings.local_llm_timeout_s: float` (default `30.0`), `Settings.external_llm_timeout_s: float` (default `30.0`), `Settings.external_model_price_per_1k_input_tokens: float` (default `0.0`), `Settings.external_model_price_per_1k_output_tokens: float` (default `0.0`). Campos já existentes `external_model_base_url`/`external_model_name` passam a apontar para OpenRouter (usados pelas Tasks 3 e 6).

- [ ] **Step 1: Escrever o teste que falha**

Adicionar ao final de `backend/tests/test_config.py`:

```python
def test_settings_have_router_defaults():
    settings = Settings(_env_file=None)
    assert settings.router_complexity_strategy == "heuristic"
    assert settings.local_llm_timeout_s == 30.0
    assert settings.external_llm_timeout_s == 30.0
    assert settings.external_model_price_per_1k_input_tokens == 0.0
    assert settings.external_model_price_per_1k_output_tokens == 0.0


def test_settings_external_model_points_to_openrouter():
    settings = Settings(_env_file=None)
    assert settings.external_model_base_url == "https://openrouter.ai/api/v1"
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: 'Settings' object has no attribute 'router_complexity_strategy'` (e outros atributos ausentes).

- [ ] **Step 3: Implementar os novos campos**

Em `backend/src/app/config.py`, substituir o bloco do modelo externo e adicionar os novos campos (mantendo o restante da classe intacto):

```python
    external_model_base_url: str = "https://openrouter.ai/api/v1"
    external_model_api_key: str = "changeme"
    # MVP: sem default fixado — decidir o modelo (formato "provider/model" do
    # OpenRouter, ex.: "anthropic/claude-3.5-haiku") na hora do benchmark real
    # (ver docs/superpowers/specs/2026-09-05-roteador-basico-design.md §6).
    external_model_name: str = ""
    external_model_price_per_1k_input_tokens: float = 0.0
    external_model_price_per_1k_output_tokens: float = 0.0

    router_complexity_strategy: str = "heuristic"
    local_llm_timeout_s: float = 30.0
    external_llm_timeout_s: float = 30.0
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_config.py -v`
Expected: PASS (4 testes).

- [ ] **Step 5: Atualizar `.env.example`**

Substituir o bloco `# --- Modelo externo (roteador, R3) ---` em `backend/.env.example` por:

```
# --- Modelo externo via OpenRouter (roteador, R3) ---
EXTERNAL_MODEL_BASE_URL=https://openrouter.ai/api/v1
EXTERNAL_MODEL_API_KEY=changeme
# MVP: sem default — formato "provider/model" (ex.: anthropic/claude-3.5-haiku)
EXTERNAL_MODEL_NAME=
EXTERNAL_MODEL_PRICE_PER_1K_INPUT_TOKENS=0.0
EXTERNAL_MODEL_PRICE_PER_1K_OUTPUT_TOKENS=0.0

# --- Roteador: estratégia de classificação (R3) ---
ROUTER_COMPLEXITY_STRATEGY=heuristic
LOCAL_LLM_TIMEOUT_S=30.0
EXTERNAL_LLM_TIMEOUT_S=30.0
```

- [ ] **Step 6: Commit**

```bash
cd backend
ruff check src/app/config.py tests/test_config.py
ruff format src/app/config.py tests/test_config.py
git add src/app/config.py tests/test_config.py .env.example
git commit -m "feat(router): adiciona config do roteador e OpenRouter (R3, Fase 1)"
```

---

## Task 2: Contrato de LLM + cliente Ollama

**Files:**
- Create: `backend/src/app/router/llm_client.py`
- Create: `backend/src/app/router/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Consumes: nenhum (task-base).
- Produces: `LLMResponse` (pydantic `BaseModel` com `text: str`, `prompt_tokens: int | None`, `completion_tokens: int | None`, `total_duration_ms: float`, `load_duration_ms: float | None`, `eval_duration_ms: float | None`, `estimated_cost_usd: float`), `LLMClient` (`Protocol` com `async def generate(self, prompt: str) -> LLMResponse`), `OllamaClient(base_url: str, model: str, timeout_s: float, client: httpx.AsyncClient | None = None)` com método `async def generate(self, prompt: str) -> LLMResponse`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_ollama_client.py`:

```python
import httpx
import pytest

from app.router.ollama_client import OllamaClient


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


async def test_ollama_client_parses_response():
    mock_response = {
        "response": "Olá!",
        "prompt_eval_count": 12,
        "eval_count": 34,
        "total_duration": 2_500_000_000,
        "load_duration": 500_000_000,
        "eval_duration": 1_800_000_000,
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    result = await client.generate("oi")

    assert result.text == "Olá!"
    assert result.prompt_tokens == 12
    assert result.completion_tokens == 34
    assert result.total_duration_ms == 2500.0
    assert result.load_duration_ms == 500.0
    assert result.eval_duration_ms == 1800.0
    assert result.estimated_cost_usd == 0.0


async def test_ollama_client_raises_on_http_error():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"error": "boom"}, status_code=500)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.generate("oi")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_ollama_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.router.ollama_client'`.

- [ ] **Step 3: Implementar `llm_client.py`**

Criar `backend/src/app/router/llm_client.py`:

```python
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
```

- [ ] **Step 4: Implementar `ollama_client.py`**

Criar `backend/src/app/router/ollama_client.py`:

```python
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
```

- [ ] **Step 5: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_ollama_client.py -v`
Expected: PASS (2 testes).

- [ ] **Step 6: Commit**

```bash
cd backend
ruff check src/app/router/llm_client.py src/app/router/ollama_client.py tests/test_ollama_client.py
ruff format src/app/router/llm_client.py src/app/router/ollama_client.py tests/test_ollama_client.py
git add src/app/router/llm_client.py src/app/router/ollama_client.py tests/test_ollama_client.py
git commit -m "feat(router): adiciona contrato LLMClient e cliente Ollama (R1, Fase 1)"
```

---

## Task 3: Cliente OpenRouter

**Files:**
- Create: `backend/src/app/router/openrouter_client.py`
- Test: `backend/tests/test_openrouter_client.py`

**Interfaces:**
- Consumes: `LLMResponse` de `app.router.llm_client` (Task 2).
- Produces: `OpenRouterClient(base_url: str, api_key: str, model: str, timeout_s: float, price_per_1k_input_tokens: float = 0.0, price_per_1k_output_tokens: float = 0.0, client: httpx.AsyncClient | None = None)` com `async def generate(self, prompt: str) -> LLMResponse`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_openrouter_client.py`:

```python
import httpx
import pytest

from app.router.openrouter_client import OpenRouterClient


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


async def test_openrouter_client_parses_response_and_computes_cost():
    mock_response = {
        "choices": [{"message": {"content": "Olá!"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        price_per_1k_input_tokens=1.0,
        price_per_1k_output_tokens=2.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    result = await client.generate("oi")

    assert result.text == "Olá!"
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.load_duration_ms is None
    assert result.eval_duration_ms is None
    assert result.estimated_cost_usd == pytest.approx(0.1 * 1.0 + 0.05 * 2.0)


async def test_openrouter_client_raises_on_http_error():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="anthropic/claude-3.5-haiku",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"error": "boom"}, status_code=401)),
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.generate("oi")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_openrouter_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.router.openrouter_client'`.

- [ ] **Step 3: Implementar**

Criar `backend/src/app/router/openrouter_client.py`:

```python
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

        return LLMResponse(
            text=data["choices"][0]["message"]["content"],
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_duration_ms=elapsed_ms,
            load_duration_ms=None,
            eval_duration_ms=None,
            estimated_cost_usd=cost,
        )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_openrouter_client.py -v`
Expected: PASS (2 testes).

- [ ] **Step 5: Commit**

```bash
cd backend
ruff check src/app/router/openrouter_client.py tests/test_openrouter_client.py
ruff format src/app/router/openrouter_client.py tests/test_openrouter_client.py
git add src/app/router/openrouter_client.py tests/test_openrouter_client.py
git commit -m "feat(router): adiciona cliente OpenRouter com estimativa de custo (R3, Fase 1)"
```

---

## Task 4: Contrato de RAG (interface + stub)

**Files:**
- Create: `backend/src/app/router/rag_client.py`
- Test: `backend/tests/test_rag_client.py`

**Interfaces:**
- Consumes: nenhum.
- Produces: `Document` (pydantic `BaseModel` com `content: str`, `source: str`, `score: float`), `RAGConnectionError(Exception)`, `RAGClient` (`Protocol` com `async def search(self, query: str, domain: str) -> list[Document]`), `NullRAGClient` (implementação stub, sempre devolve `[]`).

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_rag_client.py`:

```python
from app.router.rag_client import NullRAGClient


async def test_null_rag_client_always_returns_empty_list():
    client = NullRAGClient()

    result = await client.search("qualquer coisa", "vendas")

    assert result == []
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_rag_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.router.rag_client'`.

- [ ] **Step 3: Implementar**

Criar `backend/src/app/router/rag_client.py`:

```python
from typing import Protocol

from pydantic import BaseModel


class Document(BaseModel):
    content: str
    source: str
    score: float


class RAGConnectionError(Exception):
    """Erro de infraestrutura na busca (ex.: Qdrant fora do ar).

    Distinto de uma busca que rodou normalmente e não achou nada relevante
    — essa distinção importa para o orchestrator (ver spec §2.4): busca
    vazia é sinal de negócio válido para escalar ao externo, erro de
    infraestrutura não é.
    """


class RAGClient(Protocol):
    async def search(self, query: str, domain: str) -> list[Document]: ...


class NullRAGClient:
    # MVP: stub sem implementação real — RAG de verdade (Qdrant) entra na
    # Fase 2 (ver docs/ROADMAP.md), sem alterar o orchestrator.
    async def search(self, query: str, domain: str) -> list[Document]:
        return []
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_rag_client.py -v`
Expected: PASS (1 teste).

- [ ] **Step 5: Commit**

```bash
cd backend
ruff check src/app/router/rag_client.py tests/test_rag_client.py
ruff format src/app/router/rag_client.py tests/test_rag_client.py
git add src/app/router/rag_client.py tests/test_rag_client.py
git commit -m "feat(router): adiciona contrato RAGClient e stub NullRAGClient (R4, Fase 1)"
```

---

## Task 5: Classificador de intenção (domínio + complexidade)

**Files:**
- Create: `backend/src/app/router/classifier.py`
- Test: `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: `LLMClient`, `LLMResponse` de `app.router.llm_client` (Task 2).
- Produces: `ClassificationResult` (pydantic `BaseModel` com `domain: Literal["vendas", "suporte", "atendimento", "agendamento", "fora_escopo"]`, `complexity: Literal["baixa", "alta"]`, `confidence: float`), `async def classify(message: str, recent_messages: list[str] | None = None, strategy: str = "heuristic", llm_client: LLMClient | None = None) -> ClassificationResult`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_classifier.py`:

```python
import pytest

from app.router.classifier import ClassificationResult, classify
from app.router.llm_client import LLMResponse


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self._text = text

    async def generate(self, prompt: str) -> LLMResponse:
        return LLMResponse(text=self._text, total_duration_ms=10.0)


async def test_classify_matches_domain_by_keyword():
    result = await classify("Qual o preço desse produto?")

    assert result.domain == "vendas"
    assert result.complexity == "baixa"


async def test_classify_detects_alta_complexity_by_length():
    mensagem_longa = "Preciso de um orçamento detalhado. " * 10
    result = await classify(mensagem_longa)

    assert result.domain == "vendas"
    assert result.complexity == "alta"


async def test_classify_fallback_to_fora_escopo_when_heuristic_inconclusive():
    result = await classify("Qual a capital da França?", strategy="heuristic")

    assert result.domain == "fora_escopo"


async def test_classify_uses_recent_messages_for_context_in_heuristic_fallback():
    result = await classify(
        "sim, pode ser",
        recent_messages=["Posso agendar uma visita para você conhecer o showroom?"],
        strategy="heuristic",
    )

    assert result.domain == "agendamento"


async def test_classify_uses_llm_when_keywords_inconclusive_and_strategy_llm():
    llm_client = _FakeLLMClient('{"domain": "suporte", "complexity": "alta", "confidence": 0.9}')

    result = await classify(
        "Qual a capital da França?",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result == ClassificationResult(domain="suporte", complexity="alta", confidence=0.9)


async def test_classify_falls_back_to_heuristic_when_llm_returns_invalid_json():
    llm_client = _FakeLLMClient("isso não é json")

    result = await classify(
        "Qual a capital da França?",
        strategy="llm",
        llm_client=llm_client,
    )

    assert result.domain == "fora_escopo"


async def test_classify_raises_when_strategy_llm_without_client():
    with pytest.raises(ValueError):
        await classify("Qual a capital da França?", strategy="llm")
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.router.classifier'`.

- [ ] **Step 3: Implementar**

Criar `backend/src/app/router/classifier.py`:

```python
import json
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.router.llm_client import LLMClient

Domain = Literal["vendas", "suporte", "atendimento", "agendamento", "fora_escopo"]
Complexity = Literal["baixa", "alta"]


class ClassificationResult(BaseModel):
    domain: Domain
    complexity: Complexity
    confidence: float


# MVP: heurística simples de palavras-chave, sem NLP mais robusto — refinar
# contra o conjunto de teste de backend/eval/router_intents/ (docs/EVALUATION.md).
_DOMAIN_KEYWORDS: dict[Domain, list[str]] = {
    "vendas": ["orçamento", "comprar", "preço", "cotação", "produto"],
    "suporte": ["não funciona", "quebrado", "erro", "defeito", "problema"],
    "atendimento": ["nota fiscal", "troca", "devolução", "cancelamento", "reclamação"],
    "agendamento": ["agendar", "visita", "marcar", "horário"],
}

_COMPLEXITY_LENGTH_THRESHOLD = 280
_COMPLEXITY_QUESTION_MARK_THRESHOLD = 2

_CLASSIFIER_PROMPT_TEMPLATE = """\
Classifique a mensagem do cliente em UM dos domínios: vendas, suporte, \
atendimento, agendamento, fora_escopo. Também avalie a complexidade da \
pergunta como "baixa" ou "alta". Considere o contexto recente da conversa \
ao decidir.

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"domain": "...", "complexity": "...", "confidence": 0.0}}"""


def _match_domain_by_keywords(message: str) -> Domain | None:
    lowered = message.lower()
    matched = [
        domain for domain, keywords in _DOMAIN_KEYWORDS.items() if any(k in lowered for k in keywords)
    ]
    if len(matched) == 1:
        return matched[0]
    return None


def _heuristic_complexity(message: str) -> Complexity:
    if len(message) > _COMPLEXITY_LENGTH_THRESHOLD:
        return "alta"
    if message.count("?") >= _COMPLEXITY_QUESTION_MARK_THRESHOLD:
        return "alta"
    return "baixa"


def _classify_heuristic_fallback(message: str, recent_messages: list[str]) -> ClassificationResult:
    # MVP: histórico simples (lista de strings), sem distinguir papel
    # usuário/assistente — suficiente para resolver confirmações curtas a
    # ofertas do próprio assistente; refinar quando a memória da Fase 6
    # existir.
    combined = " ".join([*recent_messages, message])
    domain = _match_domain_by_keywords(combined) or "fora_escopo"
    return ClassificationResult(domain=domain, complexity=_heuristic_complexity(message), confidence=0.3)


async def _classify_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ClassificationResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _CLASSIFIER_PROMPT_TEMPLATE.format(contexto=contexto, mensagem=message)
    response = await llm_client.generate(prompt)
    parsed = json.loads(response.text)
    return ClassificationResult(**parsed)


async def classify(
    message: str,
    recent_messages: list[str] | None = None,
    strategy: str = "heuristic",
    llm_client: LLMClient | None = None,
) -> ClassificationResult:
    recent_messages = recent_messages or []

    domain = _match_domain_by_keywords(message)
    if domain is not None:
        return ClassificationResult(
            domain=domain, complexity=_heuristic_complexity(message), confidence=0.6
        )

    if strategy == "heuristic":
        return _classify_heuristic_fallback(message, recent_messages)

    if llm_client is None:
        raise ValueError("llm_client é obrigatório quando strategy='llm'")

    try:
        return await _classify_with_llm(message, recent_messages, llm_client)
    except (json.JSONDecodeError, ValidationError):
        return _classify_heuristic_fallback(message, recent_messages)
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_classifier.py -v`
Expected: PASS (7 testes).

- [ ] **Step 5: Commit**

```bash
cd backend
ruff check src/app/router/classifier.py tests/test_classifier.py
ruff format src/app/router/classifier.py tests/test_classifier.py
git add src/app/router/classifier.py tests/test_classifier.py
git commit -m "feat(router): adiciona classificador de intenção (regras + LLM) (R3, Fase 1)"
```

---

## Task 6: Orquestrador (lógica de decisão + log estruturado)

**Files:**
- Create: `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `LLMClient`, `LLMResponse` (Task 2); `RAGClient`, `Document`, `RAGConnectionError` (Task 4); `ClassificationResult`, `classify` (Task 5).
- Produces: `RouterDecision` (pydantic `BaseModel`), `LocalBackendIndisponivelError(Exception)`, `ExternalBackendIndisponivelError(Exception)`, `async def handle_message(message: str, recent_messages: list[str], local_client: LLMClient, external_client: LLMClient, rag_client: RAGClient, complexity_strategy: str) -> RouterDecision`.

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_orchestrator.py`:

```python
import pytest

from app.router.llm_client import LLMResponse
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    handle_message,
)
from app.router.rag_client import Document, RAGConnectionError


class _FakeLLMClient:
    def __init__(self, response: LLMResponse | None = None, exception: Exception | None = None) -> None:
        self._response = response
        self._exception = exception
        self.calls = 0

    async def generate(self, prompt: str) -> LLMResponse:
        self.calls += 1
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response


class _FakeRAGClient:
    def __init__(
        self, documents: list[Document] | None = None, exception: Exception | None = None
    ) -> None:
        self._documents = documents if documents is not None else []
        self._exception = exception

    async def search(self, query: str, domain: str) -> list[Document]:
        if self._exception is not None:
            raise self._exception
        return self._documents


def _resposta_local() -> LLMResponse:
    return LLMResponse(text="resposta local", total_duration_ms=100.0)


def _resposta_externa() -> LLMResponse:
    return LLMResponse(text="resposta externa", total_duration_ms=200.0)


async def test_agendamento_sempre_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    decisao = await handle_message(
        "quero agendar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "agendamento"
    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert local_client.calls == 1
    assert external_client.calls == 0


async def test_fora_escopo_sempre_externo_sem_tentar_rag():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("não deveria ser chamado"))

    decisao = await handle_message(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "fora_escopo"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "fora_escopo"
    assert local_client.calls == 0
    assert external_client.calls == 1


async def test_rag_vazio_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    decisao = await handle_message(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.domain == "vendas"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "rag_vazio"


async def test_rag_com_resultado_e_complexidade_baixa_fica_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    decisao = await handle_message(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"


async def test_rag_com_resultado_e_complexidade_alta_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    mensagem_longa = "Preciso de um orçamento detalhado. " * 10 + " qual o preço?"

    decisao = await handle_message(
        mensagem_longa,
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "complexidade_alta"


async def test_rag_indisponivel_propaga_erro_sem_fallback_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("qdrant fora do ar"))

    with pytest.raises(RAGConnectionError):
        await handle_message(
            "Qual o preço desse produto?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_ollama_indisponivel_nao_faz_fallback_para_externo():
    local_client = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await handle_message(
            "quero agendar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_openrouter_indisponivel_propaga_erro():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(exception=ConnectionError("openrouter fora do ar"))
    rag_client = _FakeRAGClient()

    with pytest.raises(ExternalBackendIndisponivelError):
        await handle_message(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )
```

- [ ] **Step 2: Rodar e confirmar que falha**

Run: `cd backend && python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.router.orchestrator'`.

- [ ] **Step 3: Implementar**

Criar `backend/src/app/router/orchestrator.py`:

```python
import json
import logging

from pydantic import BaseModel

from app.router.classifier import classify
from app.router.llm_client import LLMClient
from app.router.rag_client import RAGClient, RAGConnectionError

logger = logging.getLogger(__name__)

_DOMAINS_COM_RAG = {"vendas", "suporte", "atendimento"}


class RouterDecision(BaseModel):
    domain: str
    complexity: str
    confidence: float
    complexity_strategy_usada: str
    backend_escolhido: str  # "local" | "externo"
    motivo_escalonamento: str  # "fora_escopo" | "rag_vazio" | "complexidade_alta" | "nenhum"
    resposta: str
    latencia_ms: float
    tokens_entrada: int | None
    tokens_saida: int | None
    custo_estimado_usd: float


class LocalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend local (Ollama) — sem fallback automático."""


class ExternalBackendIndisponivelError(Exception):
    """Falha de infraestrutura no backend externo (OpenRouter) — sem fallback automático."""


async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
) -> RouterDecision:
    classification = await classify(
        message=message,
        recent_messages=recent_messages,
        strategy=complexity_strategy,
        llm_client=local_client,
    )

    backend_escolhido = "local"
    motivo = "nenhum"

    if classification.domain == "agendamento":
        backend_escolhido = "local"
    elif classification.domain == "fora_escopo":
        backend_escolhido = "externo"
        motivo = "fora_escopo"
    else:
        try:
            documentos = await rag_client.search(message, classification.domain)
        except RAGConnectionError:
            logger.error(
                json.dumps({"event": "rag_indisponivel", "domain": classification.domain})
            )
            raise

        if not documentos:
            backend_escolhido = "externo"
            motivo = "rag_vazio"
        elif classification.complexity == "alta":
            backend_escolhido = "externo"
            motivo = "complexidade_alta"

    client = local_client if backend_escolhido == "local" else external_client
    try:
        response = await client.generate(message)
    except Exception as exc:
        logger.error(
            json.dumps(
                {
                    "event": "backend_indisponivel",
                    "backend": backend_escolhido,
                    "domain": classification.domain,
                }
            )
        )
        if backend_escolhido == "local":
            raise LocalBackendIndisponivelError(str(exc)) from exc
        raise ExternalBackendIndisponivelError(str(exc)) from exc

    decisao = RouterDecision(
        domain=classification.domain,
        complexity=classification.complexity,
        confidence=classification.confidence,
        complexity_strategy_usada=complexity_strategy,
        backend_escolhido=backend_escolhido,
        motivo_escalonamento=motivo,
        resposta=response.text,
        latencia_ms=response.total_duration_ms,
        tokens_entrada=response.prompt_tokens,
        tokens_saida=response.completion_tokens,
        custo_estimado_usd=response.estimated_cost_usd,
    )
    logger.info(json.dumps({"event": "router_decision", **decisao.model_dump()}))
    return decisao
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (8 testes).

- [ ] **Step 5: Rodar a suíte completa**

Run: `cd backend && python -m pytest -v`
Expected: PASS — todos os testes de `tests/test_config.py`, `tests/test_ollama_client.py`, `tests/test_openrouter_client.py`, `tests/test_rag_client.py`, `tests/test_classifier.py` e `tests/test_orchestrator.py`.

- [ ] **Step 6: Commit**

```bash
cd backend
ruff check src/app/router/orchestrator.py tests/test_orchestrator.py
ruff format src/app/router/orchestrator.py tests/test_orchestrator.py
git add src/app/router/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(router): adiciona orquestrador com log estruturado de decisões (R3, Fase 1)"
```

---

## Após a implementação

Marcar em `docs/ROADMAP.md` (Fase 1) os itens correspondentes como `- [x]`:
subir modelo via Ollama (parcialmente — falta rodar de verdade, ver nota
abaixo), cliente de modelo externo via OpenRouter, classificador de
intenção, contexto de conversa no classificador, log básico de decisões.

**Não marcar como concluído neste plano** (ficam pendentes, fora de escopo
das 6 tarefas acima): rodar a avaliação comparativa real entre as 9
configurações de modelo (precisa de Ollama de verdade rodando e dos
arquivos GGUF baixados) e escrever os scripts de `backend/eval/`.
