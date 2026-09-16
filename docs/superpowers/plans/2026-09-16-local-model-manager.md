# Gerenciador de Modelos Locais (Ollama) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tela administrativa para listar os modelos locais já baixados no Ollama, trocar em runtime qual deles o chat usa, e baixar um novo (da biblioteca do Ollama ou um GGUF do Hugging Face) com progresso real, sem bloquear o backend.

**Architecture:** `OllamaClient` ganha um `model` mutável e dois métodos novos (`list_local_models`, `pull_model_streaming`, consumindo `GET /api/tags` e `POST /api/pull` do Ollama). Um router novo (`app/api/local_models.py`) expõe listar/ativar/baixar; o download roda numa `asyncio.create_task` em background, com progresso guardado num dicionário em memória (`app.state.model_pull_progress`) que o frontend consulta por polling. Frontend: nova página `/admin/modelos`.

**Tech Stack:** FastAPI + httpx (streaming), asyncio background tasks, Next.js (App Router) + TypeScript, mesmo padrão de componentes/API client já usado em `lib/api/rag.ts`/`lib/types/rag.ts`.

**Spec:** `docs/superpowers/specs/2026-09-16-local-model-manager-design.md`

## Global Constraints

- Modelo ativo só em memória (`OllamaClient.model`, mutável) — sem tabela nova no Postgres, reseta no restart do backend.
- Download nunca bloqueia a requisição HTTP que o dispara — sempre `asyncio.create_task` + `202 Accepted` imediato.
- Progresso é por camada (a mais recente em download), não agregado 0-100% do modelo inteiro — `# MVP` explícito no código.
- Não iniciar um segundo download concorrente do mesmo nome — `POST .../pull` é idempotente enquanto um pull para aquele nome já está em `"pulling"`.
- **Correção sobre a spec (descoberta durante o planejamento):** nomes de modelo podem conter `/` (`hf.co/usuario/repo`) e `:` (`llama3.1:8b`), então o endpoint de status usa `name` como **query param**, não como segmento de path (`GET /api/admin/local-models/pull-status?name=...`), não `GET .../pull/{name}/status` como a spec descreveu — um path param `{name}` quebraria em nomes com `/`. Os demais endpoints (`activate`, `pull`) já recebem `name` no corpo JSON, sem esse problema.
- Formato da API do Ollama verificado nesta sessão contra a instância local real (versão 0.30.6): `GET /api/tags` → `{"models": [{"name", "size", "modified_at", ...}]}` (confirmado com `curl`). `POST /api/pull` com `{"model": name, "stream": true}` → linhas NDJSON `{"status": "pulling manifest"}` → `{"status": "pulling <digest>", "digest", "total", "completed"}` (repetidas) → `{"status": "success"}`, ou `{"error": "<mensagem>"}` em caso de falha (a linha de erro foi confirmada ao vivo; a linha de progresso com `total`/`completed` é o formato estável e documentado publicamente da API do Ollama para essa versão, não disparado ao vivo nesta sessão de propósito, para não iniciar um download real de vários GB sem necessidade).
- Sem exclusão de modelo, sem cancelamento de download, sem persistência entre restarts, sem mudar o processo da Fase 10.

---

### Task 1: `OllamaClient` — modelo mutável + listar + baixar com progresso

**Files:**
- Modify: `backend/src/app/router/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Produces: `OllamaClient.model` (property, getter+setter, substitui o antigo `self._model` fixo); `LocalModel(name: str, size_bytes: int, modified_at: str)` (dataclass); `PullProgressLine(status: str, digest: str | None, total: int | None, completed: int | None, error: str | None)` (dataclass); `async def list_local_models(self) -> list[LocalModel]`; `async def pull_model_streaming(self, name: str) -> AsyncIterator[PullProgressLine]`.
- Consumes: nada novo — mesmo `httpx.AsyncClient` já injetável no construtor.

- [ ] **Step 1: Escrever os testes (adicionar ao arquivo existente, sem apagar os testes atuais)**

Adicionar ao topo do arquivo, junto dos imports existentes:

```python
import json

import httpx
import pytest

from app.router.ollama_client import LocalModel, OllamaClient, PullProgressLine
```

(troque a linha de import existente `from app.router.ollama_client import OllamaClient` por essa, incluindo os dois novos nomes).

Adicionar estes testes ao final do arquivo:

```python
async def test_model_property_e_setter():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({})),
    )

    assert client.model == "llama3.1:8b"

    client.model = "qwen2.5:7b"

    assert client.model == "qwen2.5:7b"


async def test_list_local_models_mapeia_a_resposta_do_ollama():
    mock_response = {
        "models": [
            {
                "name": "llama3.1:8b",
                "model": "llama3.1:8b",
                "modified_at": "2026-09-01T10:00:00Z",
                "size": 4_920_000_000,
                "digest": "sha256:abc",
                "details": {},
                "capabilities": ["completion"],
            },
            {
                "name": "qwen2.5:7b",
                "model": "qwen2.5:7b",
                "modified_at": "2026-08-15T09:00:00Z",
                "size": 4_100_000_000,
                "digest": "sha256:def",
                "details": {},
                "capabilities": ["completion"],
            },
        ]
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    modelos = await client.list_local_models()

    assert modelos == [
        LocalModel(name="llama3.1:8b", size_bytes=4_920_000_000, modified_at="2026-09-01T10:00:00Z"),
        LocalModel(name="qwen2.5:7b", size_bytes=4_100_000_000, modified_at="2026-08-15T09:00:00Z"),
    ]


async def test_list_local_models_vazio_retorna_lista_vazia():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport({"models": []})),
    )

    assert await client.list_local_models() == []


def _mock_streaming_transport(lines: list[str], status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = "\n".join(lines).encode()
        return httpx.Response(status_code, content=body)

    return httpx.MockTransport(handler)


async def test_pull_model_streaming_gera_uma_linha_por_status():
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps(
            {"status": "pulling sha256:abc", "digest": "sha256:abc", "total": 1000, "completed": 500}
        ),
        json.dumps(
            {"status": "pulling sha256:abc", "digest": "sha256:abc", "total": 1000, "completed": 1000}
        ),
        json.dumps({"status": "success"}),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    progresso = [linha async for linha in client.pull_model_streaming("llama3.1:8b")]

    assert len(progresso) == 4
    assert progresso[0] == PullProgressLine(
        status="pulling manifest", digest=None, total=None, completed=None, error=None
    )
    assert progresso[1] == PullProgressLine(
        status="pulling sha256:abc", digest="sha256:abc", total=1000, completed=500, error=None
    )
    assert progresso[3] == PullProgressLine(
        status="success", digest=None, total=None, completed=None, error=None
    )


async def test_pull_model_streaming_repassa_linha_de_erro():
    lines = [
        json.dumps({"status": "pulling manifest"}),
        json.dumps({"error": "pull model manifest: file does not exist"}),
    ]
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="llama3.1:8b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_streaming_transport(lines)),
    )

    progresso = [linha async for linha in client.pull_model_streaming("nome-invalido")]

    assert progresso[-1].error == "pull model manifest: file does not exist"
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_ollama_client.py -v`
Expected: FAIL — `ImportError: cannot import name 'LocalModel'` (e os demais, por não existirem ainda)

- [ ] **Step 3: Implementar em `backend/src/app/router/ollama_client.py`**

Substituir todo o conteúdo do arquivo por:

```python
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
            eval_duration_ms=(
                data["eval_duration"] / _NS_PER_MS if "eval_duration" in data else None
            ),
            estimated_cost_usd=0.0,
        )

    async def list_local_models(self) -> list[LocalModel]:
        """Modelos já baixados localmente (`GET /api/tags`)."""
        response = await self._client.get(
            f"{self._base_url}/api/tags", timeout=self._timeout_s
        )
        response.raise_for_status()
        data = response.json()
        return [
            LocalModel(
                name=item["name"], size_bytes=item["size"], modified_at=item["modified_at"]
            )
            for item in data.get("models", [])
        ]

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
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_ollama_client.py -v`
Expected: PASS (todos, incluindo os testes já existentes de `generate`)

- [ ] **Step 5 (verificação extra, opcional mas recomendada): confirmar o formato de linha de progresso com sucesso contra o Ollama real**

Isso NÃO deve disparar um download de verdade — use um nome de modelo que sabidamente não existe (mais barato) só para confirmar que a linha `{"status": "pulling manifest"}` aparece primeiro, OU, se quiser confirmar uma linha de progresso real (`total`/`completed`), peça autorização explícita ao usuário antes de baixar qualquer coisa nova na máquina dele — não inicie um pull de um modelo que ainda não está local sem perguntar antes.

Run: `curl -s -N -X POST http://localhost:11434/api/pull -d '{"model": "nome-que-nao-existe-xyz", "stream": true}'`
Expected: `{"status":"pulling manifest"}` seguido de uma linha `{"error": "..."}` — confirma o parser do Step 3 lida com esse formato (já coberto pelo teste do Step 1, isso é só uma confirmação a mais contra o serviço real).

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/router/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "feat(models): OllamaClient ganha model mutável, list_local_models e pull_model_streaming"
```

---

### Task 2: Schemas Pydantic (`app/models/local_models.py`)

**Files:**
- Create: `backend/src/app/models/local_models.py`

**Interfaces:**
- Produces: `LocalModelResponse`, `LocalModelsListResponse`, `ActivateModelRequest`, `PullModelRequest`, `PullStatusResponse`.

Sem lógica própria além de validação — verificação é só o import check (mesmo padrão do Task 8 do plano anterior, `docs/superpowers/plans/2026-09-15-rag-collections-config.md`).

- [ ] **Step 1: Criar `backend/src/app/models/local_models.py`**

```python
"""Schemas Pydantic do gerenciador de modelos locais (Ollama, além do
MVP) — ver docs/superpowers/specs/2026-09-16-local-model-manager-design.md.
"""

from typing import Literal

from pydantic import BaseModel, Field


class LocalModelResponse(BaseModel):
    name: str
    size_bytes: int
    modified_at: str
    is_active: bool


class LocalModelsListResponse(BaseModel):
    models: list[LocalModelResponse]
    active_model: str


class ActivateModelRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PullModelRequest(BaseModel):
    name: str = Field(..., min_length=1)


class PullStatusResponse(BaseModel):
    status: Literal["pulling", "done", "error"]
    percent: float | None = None
    detail: str | None = None
```

- [ ] **Step 2: Verificar que importa limpo**

Run: `cd backend && .venv/bin/python -c "from app.models.local_models import LocalModelResponse, LocalModelsListResponse, ActivateModelRequest, PullModelRequest, PullStatusResponse; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/src/app/models/local_models.py
git commit -m "feat(models): schemas Pydantic do gerenciador de modelos locais"
```

---

### Task 3: Endpoints (`app/api/local_models.py`)

**Files:**
- Create: `backend/src/app/api/local_models.py`
- Test: `backend/tests/test_local_models_api.py`

**Interfaces:**
- Consumes: `OllamaClient` (Task 1), schemas (Task 2).
- Produces: `GET /api/admin/local-models`, `POST /api/admin/local-models/activate`, `POST /api/admin/local-models/pull`, `GET /api/admin/local-models/pull-status` (query param `name`, **não** path param — ver Global Constraints).

- [ ] **Step 1: Escrever `backend/tests/test_local_models_api.py`**

```python
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.local_models import get_ollama_client, get_pull_progress_store
from app.api.local_models import router as local_models_router
from app.router.ollama_client import LocalModel, OllamaClient, PullProgressLine


class _FakeOllamaClient:
    """Dublê de `OllamaClient` — sem depender de um servidor Ollama real."""

    def __init__(self, models: list[LocalModel], model_ativo: str) -> None:
        self._models = models
        self.model = model_ativo
        self.pull_calls: list[str] = []
        self._pull_lines: dict[str, list[PullProgressLine]] = {}

    async def list_local_models(self) -> list[LocalModel]:
        return self._models

    def programar_pull(self, name: str, linhas: list[PullProgressLine]) -> None:
        self._pull_lines[name] = linhas

    async def pull_model_streaming(self, name: str):
        self.pull_calls.append(name)
        for linha in self._pull_lines.get(name, []):
            yield linha


def _build_app(ollama: _FakeOllamaClient, progress_store: dict | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(local_models_router)
    app.dependency_overrides[get_ollama_client] = lambda: ollama
    app.dependency_overrides[get_pull_progress_store] = lambda: (
        progress_store if progress_store is not None else {}
    )
    return app


def test_listar_modelos_marca_o_ativo(monkeypatch):
    ollama = _FakeOllamaClient(
        models=[
            LocalModel(name="llama3.1:8b", size_bytes=100, modified_at="2026-01-01"),
            LocalModel(name="qwen2.5:7b", size_bytes=200, modified_at="2026-01-02"),
        ],
        model_ativo="qwen2.5:7b",
    )
    client = TestClient(_build_app(ollama))

    response = client.get("/api/admin/local-models")

    assert response.status_code == 200
    body = response.json()
    assert body["active_model"] == "qwen2.5:7b"
    ativos = {m["name"]: m["is_active"] for m in body["models"]}
    assert ativos == {"llama3.1:8b": False, "qwen2.5:7b": True}


def test_ativar_modelo_existente_troca_o_ativo():
    ollama = _FakeOllamaClient(
        models=[LocalModel(name="llama3.1:8b", size_bytes=100, modified_at="2026-01-01")],
        model_ativo="llama3.1:8b",
    )
    client = TestClient(_build_app(ollama))

    response = client.post("/api/admin/local-models/activate", json={"name": "llama3.1:8b"})

    assert response.status_code == 204
    assert ollama.model == "llama3.1:8b"


def test_ativar_modelo_nao_baixado_retorna_404():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    client = TestClient(_build_app(ollama))

    response = client.post("/api/admin/local-models/activate", json={"name": "inexistente"})

    assert response.status_code == 404
    assert ollama.model == "llama3.1:8b"


def test_pull_dispara_download_e_devolve_202_na_hora():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "novo-modelo",
        [
            PullProgressLine(status="pulling manifest", digest=None, total=None, completed=None, error=None),
            PullProgressLine(
                status="pulling sha256:abc", digest="sha256:abc", total=1000, completed=1000, error=None
            ),
            PullProgressLine(status="success", digest=None, total=None, completed=None, error=None),
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    response = client.post("/api/admin/local-models/pull", json={"name": "novo-modelo"})

    assert response.status_code == 202
    assert response.json() == {"name": "novo-modelo"}


async def test_pull_atualiza_o_progresso_ate_done():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    ollama.programar_pull(
        "novo-modelo",
        [
            PullProgressLine(status="pulling manifest", digest=None, total=None, completed=None, error=None),
            PullProgressLine(
                status="pulling sha256:abc", digest="sha256:abc", total=1000, completed=500, error=None
            ),
            PullProgressLine(status="success", digest=None, total=None, completed=None, error=None),
        ],
    )
    progress_store: dict = {}
    client = TestClient(_build_app(ollama, progress_store))

    client.post("/api/admin/local-models/pull", json={"name": "novo-modelo"})
    # A tarefa em background roda no mesmo loop de eventos do TestClient
    # (TransportClient síncrono por baixo do capô roda o loop até
    # completar cada requisição) — como o dublê itera uma lista já pronta
    # em memória (sem I/O de verdade), a tarefa termina antes da próxima
    # requisição HTTP. Se este teste ficar flaky, trocar por um
    # `await asyncio.sleep(0)` explícito não resolveria (TestClient não
    # compartilha o loop do teste `async def`) — nesse caso, poll o
    # endpoint de status algumas vezes com um pequeno `time.sleep` entre
    # tentativas em vez de assumir conclusão imediata.
    await asyncio.sleep(0)

    response = client.get("/api/admin/local-models/pull-status", params={"name": "novo-modelo"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["percent"] == 100.0


def test_pull_duplicado_nao_dispara_segunda_tarefa():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    progress_store = {"ja-baixando": {"status": "pulling", "percent": 10.0, "detail": "..."}}
    client = TestClient(_build_app(ollama, progress_store))

    response = client.post("/api/admin/local-models/pull", json={"name": "ja-baixando"})

    assert response.status_code == 202
    assert ollama.pull_calls == []


def test_status_sem_pull_iniciado_retorna_404():
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    client = TestClient(_build_app(ollama))

    response = client.get("/api/admin/local-models/pull-status", params={"name": "nunca-baixado"})

    assert response.status_code == 404


def test_status_com_nome_contendo_barra_e_dois_pontos_funciona():
    """Regressão: nomes de modelo podem conter `/` (Hugging Face) e `:`
    (tag) — o endpoint usa `name` como query param, não path param, para
    não quebrar nesses casos."""
    ollama = _FakeOllamaClient(models=[], model_ativo="llama3.1:8b")
    progress_store = {
        "hf.co/usuario/repo:Q4_K_M": {"status": "done", "percent": 100.0, "detail": "concluído"}
    }
    client = TestClient(_build_app(ollama, progress_store))

    response = client.get(
        "/api/admin/local-models/pull-status", params={"name": "hf.co/usuario/repo:Q4_K_M"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "done"
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_local_models_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.local_models'`

- [ ] **Step 3: Implementar `backend/src/app/api/local_models.py`**

```python
"""Endpoints HTTP do gerenciador de modelos locais (Ollama, além do MVP) —
listar, ativar em runtime e baixar (biblioteca do Ollama ou GGUF do
Hugging Face) sem bloquear o backend. Ver
docs/superpowers/specs/2026-09-16-local-model-manager-design.md.

# MVP: sem autenticação (mesma limitação já aceita para `/admin/ingestao`).
Modelo ativo só em memória (`OllamaClient.model`) — não substitui nem
antecipa a Fase 10 (escolha de produção via benchmark offline, ver
docs/ROADMAP.md).
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.local_models import (
    ActivateModelRequest,
    LocalModelResponse,
    LocalModelsListResponse,
    PullModelRequest,
    PullStatusResponse,
)
from app.router.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/local-models", tags=["local-models"])


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.local_client


def get_pull_progress_store(request: Request) -> dict:
    return request.app.state.model_pull_progress


async def _consumir_pull(ollama: OllamaClient, name: str, progress_store: dict) -> None:
    """Roda em background (`asyncio.create_task`) — nunca é aguardada pela
    requisição HTTP que a disparou. Atualiza `progress_store[name]` a cada
    linha do stream; `percent` é o da camada em download no momento, não
    agregado do modelo inteiro (ver spec §2)."""
    try:
        async for linha in ollama.pull_model_streaming(name):
            if linha.error:
                progress_store[name] = {
                    "status": "error",
                    "percent": None,
                    "detail": linha.error,
                }
                logger.warning(
                    "local_model_pull_erro nome=%s erro=%s", name, linha.error
                )
                return
            percent = None
            if linha.total and linha.completed is not None:
                percent = (linha.completed / linha.total) * 100
            atual = progress_store.get(name, {})
            progress_store[name] = {
                "status": "pulling",
                "percent": percent if percent is not None else atual.get("percent"),
                "detail": linha.status,
            }
        progress_store[name] = {"status": "done", "percent": 100.0, "detail": "concluído"}
        logger.info("local_model_pull_concluido nome=%s", name)
    except Exception as exc:
        progress_store[name] = {"status": "error", "percent": None, "detail": str(exc)}
        logger.warning("local_model_pull_erro nome=%s erro=%s", name, exc)


@router.get("", response_model=LocalModelsListResponse)
async def list_local_models_endpoint(
    ollama: OllamaClient = Depends(get_ollama_client),
) -> LocalModelsListResponse:
    modelos = await ollama.list_local_models()
    ativo = ollama.model
    return LocalModelsListResponse(
        models=[
            LocalModelResponse(
                name=modelo.name,
                size_bytes=modelo.size_bytes,
                modified_at=modelo.modified_at,
                is_active=(modelo.name == ativo),
            )
            for modelo in modelos
        ],
        active_model=ativo,
    )


@router.post("/activate", status_code=204)
async def activate_model_endpoint(
    body: ActivateModelRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
) -> None:
    modelos = await ollama.list_local_models()
    if body.name not in {modelo.name for modelo in modelos}:
        raise HTTPException(
            status_code=404, detail="Modelo não encontrado entre os já baixados."
        )
    ollama.model = body.name


@router.post("/pull", status_code=202)
async def pull_model_endpoint(
    body: PullModelRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    progress_store: dict = Depends(get_pull_progress_store),
) -> dict:
    atual = progress_store.get(body.name)
    if atual is not None and atual.get("status") == "pulling":
        return {"name": body.name}

    progress_store[body.name] = {"status": "pulling", "percent": None, "detail": "iniciando..."}
    asyncio.create_task(_consumir_pull(ollama, body.name, progress_store))
    return {"name": body.name}


@router.get("/pull-status", response_model=PullStatusResponse)
async def pull_status_endpoint(
    name: str,
    progress_store: dict = Depends(get_pull_progress_store),
) -> PullStatusResponse:
    estado = progress_store.get(name)
    if estado is None:
        raise HTTPException(
            status_code=404, detail="Nenhum download iniciado para esse modelo."
        )
    return PullStatusResponse(**estado)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_local_models_api.py -v`
Expected: PASS (todos). Se `test_pull_atualiza_o_progresso_ate_done` ficar instável (a tarefa em background pode não ter terminado no momento do `GET` seguinte), troque o `await asyncio.sleep(0)` por um pequeno laço de poll (`for _ in range(20): status = client.get(...); if status.json()["status"] != "pulling": break; time.sleep(0.05)`) antes de fazer a asserção final — documente a troca no commit se precisar.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/local_models.py backend/tests/test_local_models_api.py
git commit -m "feat(models): endpoints de listar/ativar/baixar modelos locais"
```

---

### Task 4: Wiring (`app/main.py`)

**Files:**
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_main_app.py` (arquivo já existe, da entrega anterior — adicionar a este, não substituir)

**Interfaces:**
- Consumes: `local_models_router` (Task 3).
- Produces: `app.state.model_pull_progress: dict` inicializado; router registrado.

- [ ] **Step 1: Adicionar ao `backend/tests/test_main_app.py` (ao final do arquivo, mantendo os testes existentes)**

```python
def test_create_app_inicializa_o_progress_store_de_pull_de_modelos():
    app = create_app()

    assert app.state.model_pull_progress == {}


def test_rota_de_local_models_esta_registrada():
    app = create_app()
    caminhos = {rota.path for rota in app.routes}

    assert "/api/admin/local-models" in caminhos
```

Nota: a Task 13 do plano anterior (`docs/superpowers/plans/2026-09-15-rag-collections-config.md`) já documentou que checar `{rota.path for rota in app.routes}` pode não funcionar dependendo da versão instalada do FastAPI (routers incluídos podem não aparecer "achatados" em `app.routes`) — se o segundo teste falhar por causa disso, troque para `set(app.openapi()["paths"].keys())`, mesmo ajuste já validado na entrega anterior.

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd backend && .venv/bin/pytest tests/test_main_app.py -v`
Expected: FAIL — `AttributeError: 'State' object has no attribute 'model_pull_progress'` e a rota não encontrada.

- [ ] **Step 3: Atualizar `backend/src/app/main.py`**

Adicionar o import do router novo, junto dos demais imports de `app.api.*`:

```python
from app.api.local_models import router as local_models_router
```

Adicionar, logo depois da linha que cria `app.state.local_client = OllamaClient(...)`:

```python
    # Gerenciador de modelos locais (além do MVP — ver
    # docs/superpowers/specs/2026-09-16-local-model-manager-design.md).
    # Progresso de download em memória, por nome de modelo — nunca
    # persistido, reseta a cada restart do processo.
    app.state.model_pull_progress = {}
```

Adicionar, junto dos demais `app.include_router(...)`:

```python
    app.include_router(local_models_router)
```

- [ ] **Step 4: Rodar de novo**

Run: `cd backend && .venv/bin/pytest tests/test_main_app.py -v`
Expected: PASS (todos, incluindo os testes já existentes da entrega anterior)

- [ ] **Step 5: Rodar a suíte inteira do backend**

Run: `cd backend && .venv/bin/pytest tests/ -m "not qdrant and not gpu"`
Expected: PASS em tudo (backend desta entrega + tudo que já existia)

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/main.py backend/tests/test_main_app.py
git commit -m "feat(models): conecta o gerenciador de modelos locais em app.main"
```

---

### Task 5: `lib/types/localModels.ts`

**Files:**
- Create: `frontend/lib/types/localModels.ts`

**Interfaces:**
- Produces: `LocalModel`, `LocalModelsListResponse`, `PullStatus`, `PullStatusResponse`.

- [ ] **Step 1: Criar `frontend/lib/types/localModels.ts`**

```typescript
/**
 * Tipos do contrato dos endpoints do gerenciador de modelos locais (ver
 * `backend/src/app/models/local_models.py` e
 * docs/superpowers/specs/2026-09-16-local-model-manager-design.md).
 */

export interface LocalModel {
  name: string;
  size_bytes: number;
  modified_at: string;
  is_active: boolean;
}

/** Resposta de `GET /api/admin/local-models`. */
export interface LocalModelsListResponse {
  models: LocalModel[];
  active_model: string;
}

export type PullStatus = "pulling" | "done" | "error";

/** Resposta de `GET /api/admin/local-models/pull-status?name=...`. */
export interface PullStatusResponse {
  status: PullStatus;
  percent: number | null;
  detail: string | null;
}
```

- [ ] **Step 2: Verificar que compila**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem novos erros (este arquivo não é importado por ninguém ainda, então não deve gerar erro nenhum sozinho)

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types/localModels.ts
git commit -m "feat(models): tipos do gerenciador de modelos locais no frontend"
```

---

### Task 6: `lib/api/localModels.ts`

**Files:**
- Create: `frontend/lib/api/localModels.ts`

**Interfaces:**
- Consumes: tipos da Task 5.
- Produces: `LocalModelsApiError`, `listLocalModels()`, `activateModel(name)`, `pullModel(name)`, `getPullStatus(name)`.

- [ ] **Step 1: Criar `frontend/lib/api/localModels.ts`**

```typescript
import type { LocalModelsListResponse, PullStatusResponse } from "@/lib/types/localModels";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com os endpoints do gerenciador de modelos locais. */
export class LocalModelsApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "LocalModelsApiError";
    this.status = status;
  }
}

async function _extrairDetalheDeErro(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await response
    .json()
    .then((body: { detail?: string }) => body.detail)
    .catch(() => undefined);
  throw new LocalModelsApiError(detail ?? mensagemPadrao, response.status);
}

/** Lista os modelos locais via `GET /api/admin/local-models`. */
export async function listLocalModels(): Promise<LocalModelsListResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models`);
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new LocalModelsApiError("Não foi possível carregar os modelos locais. Tente novamente.", response.status);
  }

  return (await response.json()) as LocalModelsListResponse;
}

/** Ativa um modelo já baixado via `POST /api/admin/local-models/activate`. */
export async function activateModel(name: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível ativar o modelo. Tente novamente.");
  }
}

/** Dispara o download de um modelo via `POST /api/admin/local-models/pull` (não bloqueia — retorna assim que a tarefa é iniciada). */
export async function pullModel(name: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _extrairDetalheDeErro(response, "Não foi possível iniciar o download. Tente novamente.");
  }
}

/**
 * Consulta o progresso de um download via
 * `GET /api/admin/local-models/pull-status?name=...` — usado em polling
 * pelo componente de formulário de download.
 */
export async function getPullStatus(name: string): Promise<PullStatusResponse> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/admin/local-models/pull-status?name=${encodeURIComponent(name)}`,
    );
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new LocalModelsApiError("Não foi possível consultar o progresso do download.", response.status);
  }

  return (await response.json()) as PullStatusResponse;
}
```

- [ ] **Step 2: Verificar que compila**

Run: `cd frontend && npx tsc --noEmit`
Expected: sem novos erros

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api/localModels.ts
git commit -m "feat(models): funções de API do gerenciador de modelos locais"
```

---

### Task 7: `LocalModelsTable.tsx`

**Files:**
- Create: `frontend/components/admin/LocalModelsTable.tsx`
- Create: `frontend/tests/components/LocalModelsTable.test.tsx`

**Interfaces:**
- Consumes: `@/lib/api/localModels` (`activateModel`, `LocalModelsApiError` — Task 6), `@/lib/types/localModels` (Task 5).
- Produces: `LocalModelsTable({models, onChanged, onError, onSuccess})`.

- [ ] **Step 1: Escrever `frontend/tests/components/LocalModelsTable.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import type { LocalModel } from "@/lib/types/localModels";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, activateModel: vi.fn() };
});

import { activateModel, LocalModelsApiError } from "@/lib/api/localModels";

const mockedActivate = vi.mocked(activateModel);

const MODELO_ATIVO: LocalModel = {
  name: "llama3.1:8b",
  size_bytes: 4_920_000_000,
  modified_at: "2026-09-01T10:00:00Z",
  is_active: true,
};

const MODELO_INATIVO: LocalModel = {
  name: "qwen2.5:7b",
  size_bytes: 4_100_000_000,
  modified_at: "2026-08-15T09:00:00Z",
  is_active: false,
};

describe("LocalModelsTable", () => {
  beforeEach(() => {
    mockedActivate.mockReset();
  });

  it("renderiza uma linha por modelo, com badge 'Ativo'", () => {
    render(<LocalModelsTable models={[MODELO_ATIVO, MODELO_INATIVO]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText("llama3.1:8b")).toBeInTheDocument();
    expect(screen.getByText("qwen2.5:7b")).toBeInTheDocument();
    expect(screen.getByText("Ativo")).toBeInTheDocument();
  });

  it("não mostra botão Ativar na linha já ativa", () => {
    render(<LocalModelsTable models={[MODELO_ATIVO]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByRole("button", { name: "Ativar" })).not.toBeInTheDocument();
  });

  it("clicar em Ativar chama a API e notifica onChanged/onSuccess", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    const onSuccess = vi.fn();
    render(<LocalModelsTable models={[MODELO_INATIVO]} onChanged={onChanged} onError={vi.fn()} onSuccess={onSuccess} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).toHaveBeenCalledWith("qwen2.5:7b");
    expect(onChanged).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("erro ao ativar chama onError com a mensagem da API", async () => {
    const user = userEvent.setup();
    mockedActivate.mockRejectedValueOnce(new LocalModelsApiError("Modelo não encontrado entre os já baixados."));
    const onError = vi.fn();
    render(<LocalModelsTable models={[MODELO_INATIVO]} onChanged={vi.fn()} onError={onError} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(onError).toHaveBeenCalledWith("Modelo não encontrado entre os já baixados.");
  });

  it("sem modelos, mostra mensagem vazia", () => {
    render(<LocalModelsTable models={[]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText(/nenhum modelo/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/LocalModelsTable.test.tsx`
Expected: FAIL — `Cannot find module '@/components/admin/LocalModelsTable'`

- [ ] **Step 3: Implementar `frontend/components/admin/LocalModelsTable.tsx`**

```tsx
"use client";

import { useState } from "react";

import { LocalModelsApiError, activateModel } from "@/lib/api/localModels";
import type { LocalModel } from "@/lib/types/localModels";

function formatarTamanho(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  return `${gb.toFixed(1)} GB`;
}

export interface LocalModelsTableProps {
  models: LocalModel[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function LocalModelsTable({ models, onChanged, onError, onSuccess }: LocalModelsTableProps) {
  const [processando, setProcessando] = useState(false);

  async function handleAtivar(modelo: LocalModel) {
    setProcessando(true);
    try {
      await activateModel(modelo.name);
      onSuccess(`"${modelo.name}" agora é o modelo ativo no chat.`);
      onChanged();
    } catch (err) {
      onError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao ativar o modelo.");
    } finally {
      setProcessando(false);
    }
  }

  if (models.length === 0) {
    return <p className="text-sm text-gray-600">Nenhum modelo local baixado ainda.</p>;
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          <th className="py-2 pr-4">Nome</th>
          <th className="py-2 pr-4">Tamanho</th>
          <th className="py-2 pr-4" />
        </tr>
      </thead>
      <tbody>
        {models.map((modelo) => (
          <tr key={modelo.name} className="border-b border-gray-100">
            <td className="py-2 pr-4 text-gray-900">
              {modelo.name}
              {modelo.is_active && (
                <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                  Ativo
                </span>
              )}
            </td>
            <td className="py-2 pr-4 text-gray-700">{formatarTamanho(modelo.size_bytes)}</td>
            <td className="py-2 pr-4 text-right">
              {!modelo.is_active && (
                <button
                  type="button"
                  onClick={() => handleAtivar(modelo)}
                  disabled={processando}
                  className="text-gray-700 hover:text-gray-900 disabled:opacity-50"
                >
                  Ativar
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 4: Rodar de novo**

Run: `cd frontend && npx vitest run tests/components/LocalModelsTable.test.tsx`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/LocalModelsTable.tsx frontend/tests/components/LocalModelsTable.test.tsx
git commit -m "feat(models): tabela de modelos locais com ativação"
```

---

### Task 8: `PullModelForm.tsx` (com polling de progresso)

**Files:**
- Create: `frontend/components/admin/PullModelForm.tsx`
- Create: `frontend/tests/components/PullModelForm.test.tsx`

**Interfaces:**
- Consumes: `@/lib/api/localModels` (`pullModel`, `getPullStatus`, `LocalModelsApiError` — Task 6).
- Produces: `PullModelForm({onPulled})`.

- [ ] **Step 1: Escrever `frontend/tests/components/PullModelForm.test.tsx`**

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PullModelForm } from "@/components/admin/PullModelForm";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, pullModel: vi.fn(), getPullStatus: vi.fn() };
});

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";

const mockedPullModel = vi.mocked(pullModel);
const mockedGetPullStatus = vi.mocked(getPullStatus);

describe("PullModelForm", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockedPullModel.mockReset();
    mockedGetPullStatus.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("botão Baixar fica desabilitado com o campo vazio", () => {
    render(<PullModelForm onPulled={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Baixar" })).toBeDisabled();
  });

  it("submete, faz polling do status até 'done', e chama onPulled", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus
      .mockResolvedValueOnce({ status: "pulling", percent: 30, detail: "baixando..." })
      .mockResolvedValueOnce({ status: "done", percent: 100, detail: "concluído" });
    const onPulled = vi.fn();

    render(<PullModelForm onPulled={onPulled} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(mockedPullModel).toHaveBeenCalledWith("llama3.1:8b");
    expect(await screen.findByText(/30/)).toBeInTheDocument();

    await vi.advanceTimersByTimeAsync(1500);

    await waitFor(() => expect(onPulled).toHaveBeenCalled());
    expect(screen.getByText(/concluído/i)).toBeInTheDocument();
  });

  it("status 'error' para o polling e mostra a mensagem", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockResolvedValueOnce(undefined);
    mockedGetPullStatus.mockResolvedValueOnce({
      status: "error",
      percent: null,
      detail: "pull model manifest: file does not exist",
    });

    render(<PullModelForm onPulled={vi.fn()} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "nome-invalido");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText(/file does not exist/)).toBeInTheDocument();
  });

  it("erro ao disparar o pull mostra a mensagem da API", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    mockedPullModel.mockRejectedValueOnce(new LocalModelsApiError("Não foi possível iniciar o download."));

    render(<PullModelForm onPulled={vi.fn()} />);

    await user.type(screen.getByLabelText(/nome do modelo/i), "llama3.1:8b");
    await user.click(screen.getByRole("button", { name: "Baixar" }));

    expect(await screen.findByText("Não foi possível iniciar o download.")).toBeInTheDocument();
    expect(mockedGetPullStatus).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/PullModelForm.test.tsx`
Expected: FAIL — `Cannot find module '@/components/admin/PullModelForm'`

- [ ] **Step 3: Implementar `frontend/components/admin/PullModelForm.tsx`**

```tsx
"use client";

import { useEffect, useRef, useState } from "react";

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";
import type { PullStatusResponse } from "@/lib/types/localModels";

const POLL_INTERVAL_MS = 1000;

export interface PullModelFormProps {
  onPulled: () => void;
}

export function PullModelForm({ onPulled }: PullModelFormProps) {
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState<PullStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function pararPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function iniciarPolling(nomeModelo: string) {
    intervalRef.current = setInterval(async () => {
      try {
        const status = await getPullStatus(nomeModelo);
        setProgresso(status);
        if (status.status === "done") {
          pararPolling();
          setEnviando(false);
          onPulled();
        } else if (status.status === "error") {
          pararPolling();
          setEnviando(false);
          setError(status.detail ?? "Erro ao baixar o modelo.");
        }
      } catch (err) {
        pararPolling();
        setEnviando(false);
        setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao consultar o progresso.");
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nome.trim() || enviando) return;

    setEnviando(true);
    setError(null);
    setProgresso(null);

    try {
      await pullModel(nome);
      iniciarPolling(nome);
    } catch (err) {
      setEnviando(false);
      setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao iniciar o download.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="pull-model-name" className="block text-sm font-medium text-gray-900">
          Nome do modelo
        </label>
        <input
          id="pull-model-name"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="ex.: llama3.1:8b ou hf.co/usuario/repo"
          disabled={enviando}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <button
        type="submit"
        disabled={!nome.trim() || enviando}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {enviando ? "Baixando..." : "Baixar"}
      </button>

      {progresso && progresso.status === "pulling" && (
        <div className="text-sm text-gray-600">
          {progresso.percent !== null && (
            <div className="mt-1 h-2 w-full rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-gray-900"
                style={{ width: `${Math.min(100, Math.max(0, progresso.percent))}%` }}
              />
            </div>
          )}
          <p className="mt-1">
            {progresso.percent !== null ? `${progresso.percent.toFixed(0)}% — ` : ""}
            {progresso.detail}
          </p>
        </div>
      )}
      {progresso && progresso.status === "done" && (
        <p className="rounded-md bg-green-50 px-4 py-3 text-green-800">{progresso.detail ?? "Concluído."}</p>
      )}
      {error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </form>
  );
}
```

- [ ] **Step 4: Rodar de novo**

Run: `cd frontend && npx vitest run tests/components/PullModelForm.test.tsx`
Expected: PASS (todos). Se algum teste de polling ficar instável com `vi.advanceTimersByTimeAsync`, ajuste os `await` ao redor dos avanços de tempo (fake timers + promises assíncronas às vezes precisam de um `await Promise.resolve()` extra entre o avanço do timer e a asserção) — mantenha a intenção do teste (progresso intermediário visível, depois conclusão), só ajuste a mecânica de sincronização se necessário.

- [ ] **Step 5: Commit**

```bash
git add frontend/components/admin/PullModelForm.tsx frontend/tests/components/PullModelForm.test.tsx
git commit -m "feat(models): formulário de download com progresso via polling"
```

---

### Task 9: Página `/admin/modelos` + link no rodapé

**Files:**
- Create: `frontend/app/admin/modelos/page.tsx`
- Create: `frontend/tests/components/ModelosPage.test.tsx`
- Modify: `frontend/components/layout/Footer.tsx`

**Interfaces:**
- Consumes: `LocalModelsTable` (Task 7), `PullModelForm` (Task 8), `listLocalModels` (Task 6).
- Produces: página `/admin/modelos`; segundo link discreto no rodapé.

- [ ] **Step 1: Escrever `frontend/tests/components/ModelosPage.test.tsx`**

```typescript
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ModelosPage from "@/app/admin/modelos/page";
import type { LocalModelsListResponse } from "@/lib/types/localModels";

vi.mock("@/lib/api/localModels", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/localModels")>("@/lib/api/localModels");
  return { ...actual, listLocalModels: vi.fn() };
});

import { listLocalModels } from "@/lib/api/localModels";

const mockedListLocalModels = vi.mocked(listLocalModels);

const RESPOSTA: LocalModelsListResponse = {
  models: [
    { name: "llama3.1:8b", size_bytes: 4_920_000_000, modified_at: "2026-09-01T10:00:00Z", is_active: true },
  ],
  active_model: "llama3.1:8b",
};

describe("ModelosPage", () => {
  beforeEach(() => {
    mockedListLocalModels.mockReset();
    mockedListLocalModels.mockResolvedValue(RESPOSTA);
  });

  it("carrega e lista os modelos ao montar", async () => {
    render(<ModelosPage />);

    expect(await screen.findByText("llama3.1:8b")).toBeInTheDocument();
  });

  it("renderiza o formulário de download", async () => {
    render(<ModelosPage />);

    await screen.findByText("llama3.1:8b");
    expect(screen.getByLabelText(/nome do modelo/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Rodar para ver a falha**

Run: `cd frontend && npx vitest run tests/components/ModelosPage.test.tsx`
Expected: FAIL — `Cannot find module '@/app/admin/modelos/page'`

- [ ] **Step 3: Criar `frontend/app/admin/modelos/page.tsx`**

```tsx
"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para gerenciar os modelos locais do Ollama — listar, ativar em runtime e
// baixar (biblioteca do Ollama ou GGUF do Hugging Face). Não substitui nem
// antecipa a Fase 10 (escolha do LOCAL_MODEL_NAME de produção via
// benchmark offline, ver docs/ROADMAP.md). Ver
// docs/superpowers/specs/2026-09-16-local-model-manager-design.md.
import { useCallback, useEffect, useState } from "react";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import { PullModelForm } from "@/components/admin/PullModelForm";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { LocalModelsApiError, listLocalModels } from "@/lib/api/localModels";
import type { LocalModel } from "@/lib/types/localModels";

export default function ModelosPage() {
  const [modelos, setModelos] = useState<LocalModel[] | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarModelos = useCallback(async () => {
    try {
      const resposta = await listLocalModels();
      setModelos(resposta.models);
    } catch (err) {
      showToast(
        err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao carregar os modelos.",
        "error",
      );
      setModelos([]);
    }
  }, [showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarModelos();
  }, [carregarModelos]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Modelos locais (Ollama)</h1>
      <p className="mt-2 text-gray-600">
        Página interna, sem impacto na navegação pública do site. Ferramenta de teste — não
        substitui a escolha formal de modelo de produção (Fase 10 do roadmap).
      </p>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Modelos baixados</h2>
        <div className="mt-4">
          {modelos === null ? (
            <p className="text-sm text-gray-600">Carregando...</p>
          ) : (
            <LocalModelsTable
              models={modelos}
              onChanged={carregarModelos}
              onError={(message) => showToast(message, "error")}
              onSuccess={(message) => showToast(message, "success")}
            />
          )}
        </div>
      </div>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Baixar um modelo novo</h2>
        <p className="mt-1 text-sm text-gray-600">
          Nome da biblioteca do Ollama (ex.: <code>llama3.1:8b</code>) ou um GGUF do Hugging Face
          (ex.: <code>hf.co/usuario/repo:Q4_K_M</code>).
        </p>
        <div className="mt-4">
          <PullModelForm onPulled={carregarModelos} />
        </div>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
```

- [ ] **Step 4: Adicionar o segundo link discreto em `frontend/components/layout/Footer.tsx`**

Substituir o parágrafo do link existente por (mantendo o link de `/admin/ingestao` e acrescentando o novo):

```tsx
        {/* MVP: links discretos para páginas internas administrativas — não
            entram no menu principal (docs/FRONTEND.md §8), só facilitam
            achá-las durante a demonstração do TCC. */}
        <p className="mt-2 space-x-4">
          <Link href="/admin/ingestao" className="text-gray-400 hover:text-gray-600">
            Admin: ingestão de documentos (RAG)
          </Link>
          <Link href="/admin/modelos" className="text-gray-400 hover:text-gray-600">
            Admin: modelos locais
          </Link>
        </p>
```

- [ ] **Step 5: Rodar de novo, e a suíte inteira do frontend**

Run: `cd frontend && npx vitest run`
Expected: PASS em tudo

Run: `cd frontend && npx tsc --noEmit && npx eslint .`
Expected: sem erros

- [ ] **Step 6: Commit**

```bash
git add frontend/app/admin/modelos/page.tsx frontend/tests/components/ModelosPage.test.tsx frontend/components/layout/Footer.tsx
git commit -m "feat(models): página /admin/modelos e link no rodapé"
```

---

### Task 10: Documentação — `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`

**Interfaces:** nenhuma — obrigatória por `CLAUDE.md` regras 5, 6 e 9.

- [ ] **Step 1: Adicionar a nota em `docs/ARCHITECTURE.md` §5**

Inserir, no mesmo bloco de decisões "além do MVP" já existente em §5 (depois da nota mais recente registrada lá — sobre os perfis de collection do RAG):

```markdown
**Decisão registrada (além do MVP, a pedido explícito, 2026-09-16):** uma
tela administrativa (`/admin/modelos`) passa a permitir listar os modelos
locais já baixados no Ollama, trocar em runtime qual deles o chat usa, e
baixar um novo — tanto da biblioteca padrão do Ollama quanto um GGUF
hospedado no Hugging Face (`ollama pull hf.co/<usuário>/<repo>`, suportado
nativamente pelo Ollama, sem motor de inferência adicional). O download
roda em background (nunca bloqueia o backend), com progresso acompanhado
por polling a partir do frontend. A seleção de modelo ativo fica só em
memória (reseta a cada restart) e **não substitui nem antecipa** a decisão
formal da Fase 10 (escolha do `LOCAL_MODEL_NAME` de produção via benchmark
offline contra o sistema completo) — é uma ferramenta de teste manual em
paralelo. Como as entregas anteriores fora do MVP, fica registrada aqui e
no roadmap para não ser confundida com item do escopo original nem
esquecida na revisão final (Fase 11). Detalhes de implementação:
`docs/superpowers/specs/2026-09-16-local-model-manager-design.md`.
```

- [ ] **Step 2: Adicionar uma entrada em `docs/ROADMAP.md`**

Adicionar, na seção "Extra fora do MVP" já existente (junto das entregas do RAG), uma nova entrada:

```markdown
## Extra fora do MVP — Gerenciador de Modelos Locais (Ollama)

> Pedido explícito do usuário, fora do escopo original do MVP (ver
> `docs/ARCHITECTURE.md` §5 e
> `docs/superpowers/specs/2026-09-16-local-model-manager-design.md`).

- [x] **Gerenciador de modelos locais** — tela `/admin/modelos` para
      listar/ativar em runtime/baixar (Ollama ou Hugging Face GGUF) modelos
      locais de chat, sem bloquear o backend durante o download. Não
      substitui a escolha formal de produção da Fase 10.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md
git commit -m "docs: registra o gerenciador de modelos locais (Ollama) fora do MVP"
```

---

## Self-review desta plan

**Cobertura da spec:** §2 (decisões: modelo ativo em memória, download em background+polling, percentual por camada) → Tasks 1, 3, 4, 8; §3.1 (OllamaClient) → Task 1; §3.2 (endpoints, incluindo a correção de path→query param pro `name`) → Task 3; §3.3 (schemas) → Task 2; §3.4 (wiring) → Task 4; §4 (frontend) → Tasks 5-9; §5 (testes) → embutido em cada task; §6 (docs) → Task 10; §7 (não-objetivos) → respeitado em todas as tasks (sem exclusão de modelo, sem cancelamento, sem persistência, sem tocar na Fase 10).

**Desvio da spec, documentado e corrigido durante o planejamento:** a spec descrevia o endpoint de status como `GET .../pull/{name}/status` (path param); como nomes de modelo podem conter `/` e `:`, isso quebraria em nomes como `hf.co/usuario/repo:Q4_K_M`. Corrigido para `GET .../pull-status?name=...` (query param) em toda a Task 3, com um teste de regressão dedicado (`test_status_com_nome_contendo_barra_e_dois_pontos_funciona`) e a mesma correção refletida no cliente frontend (Task 6, `encodeURIComponent`).

**Consistência de tipos/assinaturas verificada:** `OllamaClient.list_local_models`/`pull_model_streaming` (Task 1) usados com as mesmas assinaturas no dublê de teste da Task 3 e na implementação real do endpoint; `LocalModel`/`PullProgressLine` (Task 1) têm os mesmos campos usados pelos endpoints (Task 3) e pelos schemas de resposta (Task 2); os tipos TypeScript (Task 5) espelham exatamente os schemas Pydantic (Task 2), incluindo `percent: number | null`/`detail: string | null` opcionais.
