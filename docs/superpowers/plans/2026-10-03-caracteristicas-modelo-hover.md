# Características de Modelo (Multimodalidade) no Hover — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ao passar o mouse (ou focar) sobre qualquer caixa de modelo em
`/admin/modelos` (OpenRouter externo, Ollama local, ou a tag digitada em
"baixar modelo"), mostrar um painel com as modalidades de entrada/saída
reais do modelo (destacando as não-textuais), contexto, e specs por fonte —
buscadas em OpenRouter/Ollama/Hugging Face e persistidas no Postgres com
staleness de 7 dias e um botão de refresh manual.

**Architecture:** Uma tabela nova (`model_characteristics`) guarda o
resultado de três fetchers (um por fonte: OpenRouter `/api/v1/models`,
Ollama `/api/show`, Hugging Face Hub `/api/models/{repo}`) por trás de um
único endpoint cache-or-fetch. O frontend busca por hook (`useModelCharacteristics`)
cacheado em memória da aba, mostrado num painel de apresentação
(`ModelCharacteristicsPanel`) dentro de um `Tooltip` estendido para aceitar
um elemento-gatilho customizado (o card inteiro) e conteúdo rico.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, httpx,
Next.js 16 (App Router), TypeScript, Tailwind, Vitest + Testing Library,
Pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md`

## Global Constraints

- Staleness do cache: 7 dias (`STALENESS = timedelta(days=7)`).
- Fonte Hugging Face só é consultada para tags que batem com `^hf\.co\/` (case-insensitive) — nunca busca por palavra-chave.
- Nenhuma falha de fonte externa pode lançar exceção não tratada até o endpoint — sempre vira `None` (404) ou serve o cache stale.
- `is_multimodal` é campo derivado (`len(set(input_modalities) - {"text"}) > 0`), nunca a forma de exibição — a UI sempre mostra a lista explícita de modalidades.
- Sem busca/catálogo navegável — as listas fixas (`POPULAR_MODELS`/`FREE_MODELS`/`POPULAR_LOCAL_PRESETS`) continuam como estão.
- Todo texto de UI em português, seguindo o estilo já usado nos componentes de `/admin/modelos`.

---

## Backend

### Task 1: Tabela `model_characteristics` (modelo SQLAlchemy + migração)

**Files:**
- Modify: `backend/src/app/db/models.py`
- Create: `backend/migrations/versions/0016_model_characteristics.py`
- Test: `backend/tests/test_db_models.py` (criar se não existir; se já existir um arquivo equivalente, adicionar o teste lá — rode `find backend/tests -iname "*db_model*"` primeiro para confirmar)

**Interfaces:**
- Produces: `app.db.models.ModelCharacteristics` (colunas: `id: uuid.UUID`, `source: str`, `tag: str`, `is_multimodal: bool`, `input_modalities: list`, `output_modalities: list`, `context_length: int | None`, `parameter_size: str | None`, `quantization: str | None`, `pricing_prompt_per_1k: float | None`, `pricing_completion_per_1k: float | None`, `knowledge_cutoff: str | None`, `raw_payload: dict`, `fetched_at: datetime`), tabela `model_characteristics` com `UniqueConstraint("source", "tag")`.

- [ ] **Step 1: Adicionar `UniqueConstraint` ao import do SQLAlchemy**

Em `backend/src/app/db/models.py`, troque a linha de import:

```python
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text, func
```

por:

```python
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, func
```

- [ ] **Step 2: Adicionar a classe `ModelCharacteristics` ao final de `db/models.py`**

```python
class ModelCharacteristics(Base):
    """Características de um modelo (multimodalidade, contexto, specs),
    buscadas em fontes externas (OpenRouter/Ollama/Hugging Face) e
    cacheadas — ver docs/superpowers/specs/2026-10-03-caracteristicas-
    modelo-hover-design.md. Staleness de 7 dias; refresh manual disponível
    via endpoint dedicado.

    # MVP: cache por tag exata, sem normalização entre fontes (a mesma
    # família de modelo pode aparecer como linhas separadas se buscada via
    # OpenRouter e via Ollama) — cada fonte+tag é uma unidade independente.
    """

    __tablename__ = "model_characteristics"
    __table_args__ = (
        UniqueConstraint("source", "tag", name="uq_model_characteristics_source_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str]
    tag: Mapped[str]
    is_multimodal: Mapped[bool] = mapped_column(Boolean, default=False)
    input_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    output_modalities: Mapped[list] = mapped_column(_JsonVariant, default=list)
    context_length: Mapped[int | None]
    parameter_size: Mapped[str | None]
    quantization: Mapped[str | None]
    pricing_prompt_per_1k: Mapped[float | None]
    pricing_completion_per_1k: Mapped[float | None]
    knowledge_cutoff: Mapped[str | None]
    raw_payload: Mapped[dict] = mapped_column(_JsonVariant, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 3: Criar a migração `0016`**

Primeiro confira a revisão mais recente: `ls backend/migrations/versions/ | sort | tail -3` (deve mostrar `0015_agendamentos.py` como a mais recente nesta base; se houver uma `0016`/`0017` criada por outra sessão enquanto isso, ajuste `revision`/`down_revision` de acordo).

Crie `backend/migrations/versions/0016_model_characteristics.py`:

```python
"""cria a tabela model_characteristics (características de modelo, hover admin)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_characteristics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("tag", sa.String(), nullable=False),
        sa.Column("is_multimodal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("input_modalities", JSONB(), nullable=False),
        sa.Column("output_modalities", JSONB(), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("parameter_size", sa.String(), nullable=True),
        sa.Column("quantization", sa.String(), nullable=True),
        sa.Column("pricing_prompt_per_1k", sa.Float(), nullable=True),
        sa.Column("pricing_completion_per_1k", sa.Float(), nullable=True),
        sa.Column("knowledge_cutoff", sa.String(), nullable=True),
        sa.Column("raw_payload", JSONB(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "tag", name="uq_model_characteristics_source_tag"),
    )


def downgrade() -> None:
    op.drop_table("model_characteristics")
```

- [ ] **Step 4: Rodar a migração contra o Postgres real e conferir**

```bash
cd backend && .venv/bin/alembic upgrade head
.venv/bin/python -c "
import asyncio
from app.db.engine import create_db_engine
from app.config import get_settings

async def main():
    engine = create_db_engine(get_settings().postgres_dsn)
    async with engine.connect() as conn:
        result = await conn.exec_driver_sql(\"SELECT column_name FROM information_schema.columns WHERE table_name='model_characteristics'\")
        print([r[0] for r in result])
    await engine.dispose()

asyncio.run(main())
"
```

Expected: lista com todas as colunas definidas no Step 3.

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0016_model_characteristics.py
git commit -m "feat(model-catalog): tabela model_characteristics (migração 0016)"
```

---

### Task 2: Schemas Pydantic (`app/models/model_catalog.py`)

**Files:**
- Create: `backend/src/app/models/model_catalog.py`
- Test: `backend/tests/test_model_catalog_schemas.py`

**Interfaces:**
- Consumes: nada (schemas puros).
- Produces: `ModelSource = Literal["openrouter", "ollama", "huggingface"]`, `ModelCharacteristicsResponse`, `CharacteristicsRefreshRequest`.

- [ ] **Step 1: Escrever o teste**

```python
# backend/tests/test_model_catalog_schemas.py
from datetime import UTC, datetime

from app.models.model_catalog import CharacteristicsRefreshRequest, ModelCharacteristicsResponse


def test_model_characteristics_response_aceita_campos_opcionais_none():
    resp = ModelCharacteristicsResponse(
        source="ollama",
        tag="llama3.1:8b",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=131072,
        parameter_size="8.0B",
        quantization="Q4_K_M",
        pricing_prompt_per_1k=None,
        pricing_completion_per_1k=None,
        knowledge_cutoff=None,
        fetched_at=datetime.now(UTC),
    )
    assert resp.is_multimodal is False
    assert resp.pricing_prompt_per_1k is None


def test_characteristics_refresh_request_exige_tag_nao_vazia():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CharacteristicsRefreshRequest(source="openrouter", tag="")
```

- [ ] **Step 2: Rodar e confirmar falha (módulo não existe ainda)**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_schemas.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.models.model_catalog'`

- [ ] **Step 3: Criar `backend/src/app/models/model_catalog.py`**

```python
"""Schemas Pydantic das características de modelo (multimodalidade,
contexto, specs) — ver docs/superpowers/specs/2026-10-03-caracteristicas-
modelo-hover-design.md.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModelSource = Literal["openrouter", "ollama", "huggingface"]


class ModelCharacteristicsResponse(BaseModel):
    source: ModelSource
    tag: str
    is_multimodal: bool
    input_modalities: list[str]
    output_modalities: list[str]
    context_length: int | None
    parameter_size: str | None
    quantization: str | None
    pricing_prompt_per_1k: float | None
    pricing_completion_per_1k: float | None
    knowledge_cutoff: str | None
    fetched_at: datetime


class CharacteristicsRefreshRequest(BaseModel):
    source: ModelSource
    tag: str = Field(..., min_length=1)
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_schemas.py -v`
Expected: PASS (2 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/models/model_catalog.py backend/tests/test_model_catalog_schemas.py
git commit -m "feat(model-catalog): schemas Pydantic de características de modelo"
```

---

### Task 3: `OllamaClient.get_model_details`

**Files:**
- Modify: `backend/src/app/router/ollama_client.py`
- Test: `backend/tests/test_ollama_client.py`

**Interfaces:**
- Produces: `async def OllamaClient.get_model_details(self, name: str) -> dict | None` — `None` em qualquer falha HTTP (modelo não baixado, erro de rede, etc.); dict cru da resposta de `/api/show` em caso de sucesso.

- [ ] **Step 1: Escrever os testes (adicionar ao final de `tests/test_ollama_client.py`)**

Primeiro confira a assinatura do helper já existente nesse arquivo: `grep -n "_mock_transport" backend/tests/test_ollama_client.py` (já usado por outros testes, aceita `json_response: dict, status_code: int = 200`). Adicione:

```python
async def test_get_model_details_retorna_dict_quando_modelo_existe():
    mock_response = {
        "capabilities": ["completion", "vision"],
        "details": {"family": "qwen2", "parameter_size": "7.6B", "quantization_level": "Q4_K_M"},
        "model_info": {"qwen2.context_length": 32768},
    }
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=_mock_transport(mock_response)),
    )

    detalhes = await client.get_model_details("qwen2.5:7b")

    assert detalhes == mock_response


async def test_get_model_details_retorna_none_quando_modelo_nao_baixado():
    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        timeout_s=30.0,
        client=httpx.AsyncClient(
            transport=_mock_transport({"error": "model not found"}, status_code=404)
        ),
    )

    assert await client.get_model_details("modelo-inexistente") is None


async def test_get_model_details_retorna_none_em_erro_de_conexao():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexão recusada", request=request)

    client = OllamaClient(
        base_url="http://localhost:11434",
        model="qwen2.5:7b",
        timeout_s=30.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    assert await client.get_model_details("qwen2.5:7b") is None
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ollama_client.py -k get_model_details -v`
Expected: FAIL com `AttributeError: 'OllamaClient' object has no attribute 'get_model_details'`

- [ ] **Step 3: Implementar em `backend/src/app/router/ollama_client.py`**

Adicione ao final da classe `OllamaClient` (depois de `pull_model_streaming`):

```python
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
        except httpx.HTTPError:
            return None
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ollama_client.py -k get_model_details -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Rodar a suíte inteira do arquivo para garantir que nada quebrou**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ollama_client.py -v`
Expected: todos PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/router/ollama_client.py backend/tests/test_ollama_client.py
git commit -m "feat(ollama): OllamaClient.get_model_details via /api/show"
```

---

### Task 4: Fetcher OpenRouter (`app/model_catalog/characteristics.py`, parte 1)

**Files:**
- Create: `backend/src/app/model_catalog/__init__.py` (vazio)
- Create: `backend/src/app/model_catalog/characteristics.py`
- Test: `backend/tests/test_model_catalog_characteristics.py`

**Interfaces:**
- Produces: `ModelSource` (re-exportado de `app.models.model_catalog`), `OPENROUTER_MODELS_URL: str`, `async def _fetch_openrouter(tag: str, http_client: httpx.AsyncClient) -> dict | None` — dict com chaves `input_modalities: list[str]`, `output_modalities: list[str]`, `context_length: int | None`, `pricing_prompt_per_1k: float | None`, `pricing_completion_per_1k: float | None`, `knowledge_cutoff: str | None`, `raw_payload: dict`. `None` se a tag não existir na lista do OpenRouter ou a chamada falhar.

- [ ] **Step 1: Criar o pacote vazio**

```bash
mkdir -p backend/src/app/model_catalog
touch backend/src/app/model_catalog/__init__.py
```

- [ ] **Step 2: Escrever o teste**

```python
# backend/tests/test_model_catalog_characteristics.py
import httpx
import pytest

from app.model_catalog.characteristics import _fetch_openrouter


def _mock_openrouter_transport(models: list[dict]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": models})

    return httpx.MockTransport(handler)


async def test_fetch_openrouter_mapeia_modelo_multimodal():
    models = [
        {
            "id": "openai/gpt-4o-mini",
            "context_length": 128000,
            "architecture": {
                "input_modalities": ["text", "image", "file"],
                "output_modalities": ["text"],
            },
            "pricing": {"prompt": "0.00000015", "completion": "0.0000006"},
            "knowledge_cutoff": "2023-10-31",
        }
    ]
    http_client = httpx.AsyncClient(transport=_mock_openrouter_transport(models))

    resultado = await _fetch_openrouter("openai/gpt-4o-mini", http_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image", "file"]
    assert resultado["output_modalities"] == ["text"]
    assert resultado["context_length"] == 128000
    assert resultado["pricing_prompt_per_1k"] == pytest.approx(0.00000015 * 1000)
    assert resultado["pricing_completion_per_1k"] == pytest.approx(0.0000006 * 1000)
    assert resultado["knowledge_cutoff"] == "2023-10-31"
    assert resultado["raw_payload"] == models[0]


async def test_fetch_openrouter_tag_inexistente_retorna_none():
    http_client = httpx.AsyncClient(transport=_mock_openrouter_transport([{"id": "outro/modelo"}]))

    assert await _fetch_openrouter("nao/existe", http_client) is None


async def test_fetch_openrouter_erro_de_rede_retorna_none():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rede", request=request)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert await _fetch_openrouter("openai/gpt-4o-mini", http_client) is None


async def test_fetch_openrouter_cacheia_lista_entre_chamadas():
    """Duas tags pedidas em sequência não devem disparar duas requisições —
    a lista completa (466 modelos reais) é cacheada em memória do processo
    por 1h (ver spec §2)."""
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    chamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas["n"] += 1
        return httpx.Response(
            200, json={"data": [{"id": "a/a"}, {"id": "b/b", "context_length": 1000}]}
        )

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await _fetch_openrouter("a/a", http_client)
    await _fetch_openrouter("b/b", http_client)

    assert chamadas["n"] == 1
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -v`
Expected: FAIL com `ModuleNotFoundError`

- [ ] **Step 4: Implementar `backend/src/app/model_catalog/characteristics.py` (só a parte do OpenRouter por enquanto)**

```python
"""Busca e cache de características de modelo (multimodalidade, contexto,
specs) em três fontes externas — ver docs/superpowers/specs/2026-10-03-
caracteristicas-modelo-hover-design.md.

# MVP: cada fonte tem seu próprio fetcher best-effort (nunca lança exceção
# até o chamador — falha vira `None`); a persistência/staleness fica em
# `get_or_fetch`, adicionada nas próximas tasks deste plano.
"""

import time
from datetime import timedelta
from typing import Any

import httpx

from app.models.model_catalog import ModelSource

STALENESS = timedelta(days=7)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_CACHE_TTL_S = 3600  # 1h — ver spec §2 (lista de 466 modelos não muda a cada minuto)

# Cache em memória do processo da lista completa do OpenRouter — evita
# rebaixar ~466 modelos a cada tag diferente pedida em sequência.
_openrouter_cache: dict[str, Any] = {"models": None, "fetched_at": None}


async def _get_openrouter_catalog(http_client: httpx.AsyncClient) -> list[dict] | None:
    agora = time.monotonic()
    cache_valido = (
        _openrouter_cache["models"] is not None
        and _openrouter_cache["fetched_at"] is not None
        and (agora - _openrouter_cache["fetched_at"]) < _OPENROUTER_CACHE_TTL_S
    )
    if cache_valido:
        return _openrouter_cache["models"]

    try:
        response = await http_client.get(OPENROUTER_MODELS_URL, timeout=10.0)
        response.raise_for_status()
        modelos = response.json().get("data", [])
    except httpx.HTTPError:
        return _openrouter_cache["models"]  # stale-se-houver, senão None

    _openrouter_cache["models"] = modelos
    _openrouter_cache["fetched_at"] = agora
    return modelos


async def _fetch_openrouter(tag: str, http_client: httpx.AsyncClient) -> dict[str, Any] | None:
    """`source="openrouter"` — ver docs/superpowers/specs/2026-10-03-
    caracteristicas-modelo-hover-design.md §2 (fonte 1)."""
    modelos = await _get_openrouter_catalog(http_client)
    if not modelos:
        return None

    item = next((m for m in modelos if m.get("id") == tag), None)
    if item is None:
        return None

    arquitetura = item.get("architecture") or {}
    pricing = item.get("pricing") or {}

    def _preco_por_1k(valor: str | None) -> float | None:
        if valor is None:
            return None
        try:
            return float(valor) * 1000
        except (TypeError, ValueError):
            return None

    return {
        "input_modalities": arquitetura.get("input_modalities") or ["text"],
        "output_modalities": arquitetura.get("output_modalities") or ["text"],
        "context_length": item.get("context_length"),
        "pricing_prompt_per_1k": _preco_por_1k(pricing.get("prompt")),
        "pricing_completion_per_1k": _preco_por_1k(pricing.get("completion")),
        "knowledge_cutoff": item.get("knowledge_cutoff"),
        "raw_payload": item,
    }
```

- [ ] **Step 5: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -v`
Expected: PASS (4 testes)

- [ ] **Step 6: Commit**

```bash
git add backend/src/app/model_catalog/ backend/tests/test_model_catalog_characteristics.py
git commit -m "feat(model-catalog): fetcher de características via OpenRouter"
```

---

### Task 5: Fetcher Ollama (`characteristics.py`, parte 2)

**Files:**
- Modify: `backend/src/app/model_catalog/characteristics.py`
- Modify: `backend/tests/test_model_catalog_characteristics.py`

**Interfaces:**
- Consumes: `OllamaClient.get_model_details(name: str) -> dict | None` (Task 3).
- Produces: `async def _fetch_ollama(tag: str, ollama_client: "OllamaClient") -> dict | None` — mesmo formato de dict do fetcher do OpenRouter (`input_modalities`, `output_modalities`, `context_length`, `parameter_size`, `quantization`, `raw_payload`; `pricing_*`/`knowledge_cutoff` sempre `None`).

- [ ] **Step 1: Escrever os testes (adicionar ao arquivo existente)**

```python
from unittest.mock import AsyncMock

from app.model_catalog.characteristics import _fetch_ollama


async def test_fetch_ollama_modelo_com_visao():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(
        return_value={
            "capabilities": ["completion", "vision"],
            "details": {"parameter_size": "7.6B", "quantization_level": "Q4_K_M"},
            "model_info": {"qwen2vl.context_length": 32768},
        }
    )

    resultado = await _fetch_ollama("qwen2-vl:7b", ollama_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image"]
    assert resultado["output_modalities"] == ["text"]
    assert resultado["context_length"] == 32768
    assert resultado["parameter_size"] == "7.6B"
    assert resultado["quantization"] == "Q4_K_M"


async def test_fetch_ollama_modelo_so_texto():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(
        return_value={
            "capabilities": ["completion", "tools"],
            "details": {"parameter_size": "14.8B", "quantization_level": "Q4_K_M"},
            "model_info": {"qwen2.context_length": 131072},
        }
    )

    resultado = await _fetch_ollama("qwen2.5-coder:14b", ollama_client)

    assert resultado["input_modalities"] == ["text"]


async def test_fetch_ollama_modelo_nao_baixado_retorna_none():
    ollama_client = AsyncMock()
    ollama_client.get_model_details = AsyncMock(return_value=None)

    assert await _fetch_ollama("modelo-inexistente", ollama_client) is None
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -k fetch_ollama -v`
Expected: FAIL com `ImportError: cannot import name '_fetch_ollama'`

- [ ] **Step 3: Implementar — adicionar ao final de `characteristics.py`**

```python
def _context_length_do_model_info(model_info: dict[str, Any]) -> int | None:
    for chave, valor in model_info.items():
        if chave.endswith(".context_length") and isinstance(valor, int):
            return valor
    return None


async def _fetch_ollama(tag: str, ollama_client: Any) -> dict[str, Any] | None:
    """`source="ollama"` — só funciona para modelo já baixado (`/api/show`
    não existe para modelos não baixados). Ver spec §2 (fonte 2).
    `ollama_client` é duck-typed (`OllamaClient`, precisa de
    `get_model_details(name) -> dict | None`)."""
    detalhes = await ollama_client.get_model_details(tag)
    if detalhes is None:
        return None

    capabilities = detalhes.get("capabilities") or []
    input_modalities = ["text", "image"] if "vision" in capabilities else ["text"]
    details = detalhes.get("details") or {}
    model_info = detalhes.get("model_info") or {}

    return {
        "input_modalities": input_modalities,
        "output_modalities": ["text"],
        "context_length": _context_length_do_model_info(model_info),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "pricing_prompt_per_1k": None,
        "pricing_completion_per_1k": None,
        "knowledge_cutoff": None,
        "raw_payload": detalhes,
    }
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -v`
Expected: PASS (7 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/model_catalog/characteristics.py backend/tests/test_model_catalog_characteristics.py
git commit -m "feat(model-catalog): fetcher de características via Ollama /api/show"
```

---

### Task 6: Fetcher Hugging Face (`characteristics.py`, parte 3)

**Files:**
- Modify: `backend/src/app/model_catalog/characteristics.py`
- Modify: `backend/tests/test_model_catalog_characteristics.py`

**Interfaces:**
- Produces: `PIPELINE_TAG_MODALIDADES: dict[str, tuple[list[str], list[str]]]`, `HUGGINGFACE_MODELS_URL: str`, `async def _fetch_huggingface(tag: str, http_client: httpx.AsyncClient) -> dict | None` — `None` imediato se `tag` não casar com `hf.co/` (sem chamada de rede).

- [ ] **Step 1: Escrever os testes**

```python
from app.model_catalog.characteristics import _fetch_huggingface


def _mock_hf_transport(payload: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload)

    return httpx.MockTransport(handler)


async def test_fetch_huggingface_modelo_multimodal():
    payload = {"pipeline_tag": "image-text-to-text", "tags": ["multimodal"]}
    http_client = httpx.AsyncClient(transport=_mock_hf_transport(payload))

    resultado = await _fetch_huggingface("hf.co/Qwen/Qwen2.5-VL-7B-Instruct", http_client)

    assert resultado is not None
    assert resultado["input_modalities"] == ["text", "image"]
    assert resultado["output_modalities"] == ["text"]


async def test_fetch_huggingface_remove_sufixo_de_quantizacao():
    capturado = {}

    def handler(request: httpx.Request) -> httpx.Response:
        capturado["path"] = request.url.path
        return httpx.Response(200, json={"pipeline_tag": "text-generation"})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    await _fetch_huggingface("hf.co/usuario/repo:Q4_K_M", http_client)

    assert capturado["path"] == "/api/models/usuario/repo"


async def test_fetch_huggingface_pipeline_tag_desconhecido():
    http_client = httpx.AsyncClient(transport=_mock_hf_transport({"pipeline_tag": "algo-novo"}))

    resultado = await _fetch_huggingface("hf.co/usuario/repo", http_client)

    assert resultado["input_modalities"] == ["desconhecido"]
    assert resultado["output_modalities"] == ["desconhecido"]


async def test_fetch_huggingface_tag_sem_prefixo_hf_co_retorna_none_sem_chamar_rede():
    chamou = {"sim": False}

    def handler(request: httpx.Request) -> httpx.Response:
        chamou["sim"] = True
        return httpx.Response(200, json={})

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    assert await _fetch_huggingface("llama3.1:8b", http_client) is None
    assert chamou["sim"] is False


async def test_fetch_huggingface_repo_inexistente_retorna_none():
    http_client = httpx.AsyncClient(transport=_mock_hf_transport({}, status_code=404))

    assert await _fetch_huggingface("hf.co/usuario/nao-existe", http_client) is None
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -k fetch_huggingface -v`
Expected: FAIL com `ImportError`

- [ ] **Step 3: Implementar — adicionar ao final de `characteristics.py`**

```python
HUGGINGFACE_MODELS_URL = "https://huggingface.co/api/models"

PIPELINE_TAG_MODALIDADES: dict[str, tuple[list[str], list[str]]] = {
    "text-generation": (["text"], ["text"]),
    "text2text-generation": (["text"], ["text"]),
    "image-text-to-text": (["text", "image"], ["text"]),
    "visual-question-answering": (["text", "image"], ["text"]),
    "image-to-text": (["image"], ["text"]),
    "automatic-speech-recognition": (["audio"], ["text"]),
    "audio-text-to-text": (["text", "audio"], ["text"]),
    "any-to-any": (["text", "image", "audio"], ["text", "image", "audio"]),
}


def _repo_do_tag_huggingface(tag: str) -> str | None:
    if not tag.lower().startswith("hf.co/"):
        return None
    sem_prefixo = tag[len("hf.co/") :]
    return sem_prefixo.split(":", 1)[0]


async def _fetch_huggingface(tag: str, http_client: httpx.AsyncClient) -> dict[str, Any] | None:
    """`source="huggingface"` — só para tags `hf.co/<usuario>/<repo>[:quant]`
    ainda não baixadas (único caso em que nem OpenRouter nem Ollama têm
    informação). Ver spec §2 (fonte 3)."""
    repo = _repo_do_tag_huggingface(tag)
    if repo is None:
        return None

    try:
        response = await http_client.get(f"{HUGGINGFACE_MODELS_URL}/{repo}", timeout=10.0)
        response.raise_for_status()
        dados = response.json()
    except httpx.HTTPError:
        return None

    pipeline_tag = dados.get("pipeline_tag")
    input_modalities, output_modalities = PIPELINE_TAG_MODALIDADES.get(
        pipeline_tag, (["desconhecido"], ["desconhecido"])
    )

    return {
        "input_modalities": input_modalities,
        "output_modalities": output_modalities,
        "context_length": None,
        "parameter_size": None,
        "quantization": None,
        "pricing_prompt_per_1k": None,
        "pricing_completion_per_1k": None,
        "knowledge_cutoff": None,
        "raw_payload": dados,
    }
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -v`
Expected: PASS (12 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/model_catalog/characteristics.py backend/tests/test_model_catalog_characteristics.py
git commit -m "feat(model-catalog): fetcher de características via Hugging Face Hub"
```

---

### Task 7: `get_or_fetch` — cache Postgres com staleness e refresh manual

**Files:**
- Modify: `backend/src/app/model_catalog/characteristics.py`
- Modify: `backend/tests/test_model_catalog_characteristics.py`

**Interfaces:**
- Consumes: `_fetch_openrouter`, `_fetch_ollama`, `_fetch_huggingface` (Tasks 4-6); `app.db.models.ModelCharacteristics` (Task 1).
- Produces: `async def get_or_fetch(session: AsyncSession, source: ModelSource, tag: str, *, force_refresh: bool = False, ollama_client: Any = None, http_client: httpx.AsyncClient | None = None) -> ModelCharacteristics | None`.

- [ ] **Step 1: Escrever os testes**

```python
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.db.models import ModelCharacteristics
from app.model_catalog.characteristics import get_or_fetch


@pytest.fixture
def http_client_openrouter_ok():
    payload = [{"id": "openai/gpt-4o-mini", "context_length": 128000, "architecture": {}}]

    def handler(request):
        return httpx.Response(200, json={"data": payload})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_get_or_fetch_busca_e_salva_quando_nao_existe(db_session, http_client_openrouter_ok):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_openrouter_ok
    )

    assert resultado is not None
    assert resultado.source == "openrouter"
    assert resultado.tag == "openai/gpt-4o-mini"
    assert resultado.context_length == 128000

    linhas = (await db_session.execute(select(ModelCharacteristics))).scalars().all()
    assert len(linhas) == 1


async def test_get_or_fetch_cache_fresco_nao_rechama_a_fonte(db_session):
    existente = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=True,
        input_modalities=["text", "image"],
        output_modalities=["text"],
        context_length=128000,
        raw_payload={},
        fetched_at=datetime.now(UTC),
    )
    db_session.add(existente)
    await db_session.commit()

    http_client_nao_deve_ser_chamado = AsyncMock()

    resultado = await get_or_fetch(
        db_session,
        "openrouter",
        "openai/gpt-4o-mini",
        http_client=http_client_nao_deve_ser_chamado,
    )

    assert resultado.id == existente.id
    http_client_nao_deve_ser_chamado.get.assert_not_called()


async def test_get_or_fetch_cache_stale_rechama_e_atualiza(db_session, http_client_openrouter_ok):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    antigo = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=1,
        raw_payload={},
        fetched_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(antigo)
    await db_session.commit()
    id_antigo = antigo.id

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_openrouter_ok
    )

    assert resultado.id == id_antigo  # upsert na mesma linha, não duplica
    assert resultado.context_length == 128000


async def test_get_or_fetch_force_refresh_ignora_cache_fresco(db_session, http_client_openrouter_ok):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    fresco = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=1,
        raw_payload={},
        fetched_at=datetime.now(UTC),
    )
    db_session.add(fresco)
    await db_session.commit()

    resultado = await get_or_fetch(
        db_session,
        "openrouter",
        "openai/gpt-4o-mini",
        force_refresh=True,
        http_client=http_client_openrouter_ok,
    )

    assert resultado.context_length == 128000


async def test_get_or_fetch_falha_com_cache_stale_serve_o_stale(db_session):
    def handler(request):
        raise httpx.ConnectError("sem rede", request=request)

    http_client_falho = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    antigo = ModelCharacteristics(
        source="openrouter",
        tag="openai/gpt-4o-mini",
        is_multimodal=False,
        input_modalities=["text"],
        output_modalities=["text"],
        context_length=42,
        raw_payload={},
        fetched_at=datetime.now(UTC) - timedelta(days=8),
    )
    db_session.add(antigo)
    await db_session.commit()

    resultado = await get_or_fetch(
        db_session, "openrouter", "openai/gpt-4o-mini", http_client=http_client_falho
    )

    assert resultado is not None
    assert resultado.context_length == 42  # continua servindo o stale


async def test_get_or_fetch_falha_sem_cache_nenhum_retorna_none(db_session):
    def handler(request):
        raise httpx.ConnectError("sem rede", request=request)

    http_client_falho = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    resultado = await get_or_fetch(
        db_session, "openrouter", "tag/nunca-visto", http_client=http_client_falho
    )

    assert resultado is None
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -k get_or_fetch -v`
Expected: FAIL com `ImportError: cannot import name 'get_or_fetch'`

- [ ] **Step 3: Implementar — adicionar ao final de `characteristics.py`**

```python
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelCharacteristics

_FETCHERS = {
    "openrouter": lambda tag, ollama_client, http_client: _fetch_openrouter(tag, http_client),
    "ollama": lambda tag, ollama_client, http_client: _fetch_ollama(tag, ollama_client),
    "huggingface": lambda tag, ollama_client, http_client: _fetch_huggingface(tag, http_client),
}


async def _buscar_linha(session: AsyncSession, source: str, tag: str) -> ModelCharacteristics | None:
    result = await session.execute(
        select(ModelCharacteristics).where(
            ModelCharacteristics.source == source, ModelCharacteristics.tag == tag
        )
    )
    return result.scalars().first()


def _esta_fresco(linha: ModelCharacteristics) -> bool:
    fetched_at = linha.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    return (datetime.now(UTC) - fetched_at) < STALENESS


async def get_or_fetch(
    session: AsyncSession,
    source: ModelSource,
    tag: str,
    *,
    force_refresh: bool = False,
    ollama_client: Any = None,
    http_client: httpx.AsyncClient | None = None,
) -> ModelCharacteristics | None:
    """Cache-first: devolve a linha do Postgres se fresca (< 7 dias); senão
    busca na fonte (`_FETCHERS[source]`) e faz upsert. `force_refresh=True`
    ignora a frescura e sempre busca de novo. Falha na busca com uma linha
    stale existente → serve a stale (nunca quebra a tela); falha sem
    nenhuma linha → `None`. Ver spec §2."""
    linha_existente = await _buscar_linha(session, source, tag)

    if linha_existente is not None and not force_refresh and _esta_fresco(linha_existente):
        return linha_existente

    dados = await _FETCHERS[source](tag, ollama_client, http_client)

    if dados is None:
        return linha_existente  # stale-se-houver, senão None

    is_multimodal = len(set(dados["input_modalities"]) - {"text"}) > 0

    if linha_existente is not None:
        for campo, valor in dados.items():
            setattr(linha_existente, campo, valor)
        linha_existente.is_multimodal = is_multimodal
        linha_existente.fetched_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(linha_existente)
        return linha_existente

    nova_linha = ModelCharacteristics(source=source, tag=tag, is_multimodal=is_multimodal, **dados)
    session.add(nova_linha)
    await session.commit()
    await session.refresh(nova_linha)
    return nova_linha
```

Remova o import duplicado de `httpx`/`Any`/`ModelSource` se já estiverem no topo do arquivo (consolide os imports no topo do módulo em vez de repetir — confira o estado final do arquivo após este step).

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_characteristics.py -v`
Expected: PASS (todos os testes do arquivo, ~19)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/model_catalog/characteristics.py backend/tests/test_model_catalog_characteristics.py
git commit -m "feat(model-catalog): get_or_fetch com cache Postgres, staleness e refresh manual"
```

---

### Task 8: Endpoints HTTP (`app/api/model_catalog.py`) + wiring

**Files:**
- Create: `backend/src/app/api/model_catalog.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_model_catalog_api.py`

**Interfaces:**
- Consumes: `get_or_fetch` (Task 7), `app.api.rag_dependencies.get_db_session`.
- Produces: `GET /api/admin/model-catalog/characteristics?source=...&tag=...`, `POST /api/admin/model-catalog/characteristics/refresh`.

- [ ] **Step 1: Escrever os testes**

```python
# backend/tests/test_model_catalog_api.py
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.model_catalog import router as model_catalog_router
from app.api.rag_dependencies import get_db_session


def _build_app(db_session, ollama_client=None, http_client=None) -> FastAPI:
    from app.api import model_catalog as mod

    app = FastAPI()
    app.include_router(model_catalog_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[mod.get_ollama_client] = lambda: ollama_client
    app.dependency_overrides[mod.get_model_catalog_http_client] = lambda: http_client
    return app


def _http_client_openrouter_ok() -> httpx.AsyncClient:
    payload = [{"id": "openai/gpt-4o-mini", "context_length": 128000, "architecture": {}}]

    def handler(request):
        return httpx.Response(200, json={"data": payload})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_get_characteristics_200_quando_encontrado(db_session):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=_http_client_openrouter_ok())
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "openrouter", "tag": "openai/gpt-4o-mini"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tag"] == "openai/gpt-4o-mini"
    assert body["context_length"] == 128000


def test_get_characteristics_404_quando_nao_encontrado(db_session):
    def handler(request):
        return httpx.Response(200, json={"data": []})

    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "openrouter", "tag": "nao/existe"},
    )

    assert response.status_code == 404


def test_get_characteristics_source_invalido_422(db_session):
    app = _build_app(db_session)
    client = TestClient(app)

    response = client.get(
        "/api/admin/model-catalog/characteristics",
        params={"source": "invalido", "tag": "x"},
    )

    assert response.status_code == 422


def test_refresh_characteristics_forca_nova_busca(db_session):
    import app.model_catalog.characteristics as mod

    mod._openrouter_cache["models"] = None
    mod._openrouter_cache["fetched_at"] = None

    app = _build_app(db_session, http_client=_http_client_openrouter_ok())
    client = TestClient(app)

    response = client.post(
        "/api/admin/model-catalog/characteristics/refresh",
        json={"source": "openrouter", "tag": "openai/gpt-4o-mini"},
    )

    assert response.status_code == 200
    assert response.json()["context_length"] == 128000
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.model_catalog'`

- [ ] **Step 3: Criar `backend/src/app/api/model_catalog.py`**

```python
"""Endpoints HTTP das características de modelo (multimodalidade, contexto,
specs) — ver docs/superpowers/specs/2026-10-03-caracteristicas-modelo-
hover-design.md.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.model_catalog.characteristics import get_or_fetch
from app.models.model_catalog import (
    CharacteristicsRefreshRequest,
    ModelCharacteristicsResponse,
    ModelSource,
)
from app.router.ollama_client import OllamaClient

router = APIRouter(prefix="/api/admin/model-catalog", tags=["model-catalog"])


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.local_client


def get_model_catalog_http_client(request: Request):
    return request.app.state.model_catalog_http_client


def _to_response(linha) -> ModelCharacteristicsResponse:
    return ModelCharacteristicsResponse(
        source=linha.source,
        tag=linha.tag,
        is_multimodal=linha.is_multimodal,
        input_modalities=linha.input_modalities,
        output_modalities=linha.output_modalities,
        context_length=linha.context_length,
        parameter_size=linha.parameter_size,
        quantization=linha.quantization,
        pricing_prompt_per_1k=linha.pricing_prompt_per_1k,
        pricing_completion_per_1k=linha.pricing_completion_per_1k,
        knowledge_cutoff=linha.knowledge_cutoff,
        fetched_at=linha.fetched_at,
    )


@router.get("/characteristics", response_model=ModelCharacteristicsResponse)
async def get_characteristics(
    source: ModelSource,
    tag: str,
    session: AsyncSession = Depends(get_db_session),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    http_client=Depends(get_model_catalog_http_client),
):
    linha = await get_or_fetch(
        session, source, tag, ollama_client=ollama_client, http_client=http_client
    )
    if linha is None:
        raise HTTPException(404, detail=f"Características não encontradas para {source}:{tag}.")
    return _to_response(linha)


@router.post("/characteristics/refresh", response_model=ModelCharacteristicsResponse)
async def refresh_characteristics(
    payload: CharacteristicsRefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    http_client=Depends(get_model_catalog_http_client),
):
    linha = await get_or_fetch(
        session,
        payload.source,
        payload.tag,
        force_refresh=True,
        ollama_client=ollama_client,
        http_client=http_client,
    )
    if linha is None:
        raise HTTPException(
            404, detail=f"Características não encontradas para {payload.source}:{payload.tag}."
        )
    return _to_response(linha)
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd backend && .venv/bin/python -m pytest tests/test_model_catalog_api.py -v`
Expected: PASS (4 testes)

- [ ] **Step 5: Wiring em `backend/src/app/main.py`**

Adicione o import (ordem alfabética, junto dos outros `from app.api.*`):

```python
from app.api.model_catalog import router as model_catalog_router
```

Adicione, logo depois da linha `app.state.crawler_http_client = httpx.AsyncClient()`:

```python
    # Cliente HTTP dedicado às fontes públicas de características de
    # modelo (OpenRouter/Hugging Face, além do MVP — ver
    # docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-
    # design.md) — separado dos demais clientes HTTP por propósito.
    app.state.model_catalog_http_client = httpx.AsyncClient()
```

Adicione `app.include_router(model_catalog_router)` junto dos outros `app.include_router(...)`.

- [ ] **Step 6: Subir o backend real e testar manualmente**

```bash
cd backend && .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 &
sleep 3
curl -s "http://localhost:8000/api/admin/model-catalog/characteristics?source=openrouter&tag=openai/gpt-4o-mini" | python3 -m json.tool
curl -s "http://localhost:8000/api/admin/model-catalog/characteristics?source=ollama&tag=qwen2.5-coder:14b-local" | python3 -m json.tool
kill %1
```

Expected: o primeiro devolve 200 com `input_modalities` incluindo `"image"`; o segundo devolve 200 com `input_modalities: ["text"]` (ou 404 se esse modelo não estiver mais baixado na sua máquina — troque pela tag de algum modelo que `ollama list` mostrar).

- [ ] **Step 7: Rodar a suíte completa do backend**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: todos PASS, incluindo os testes novos.

- [ ] **Step 8: Commit**

```bash
git add backend/src/app/api/model_catalog.py backend/src/app/main.py backend/tests/test_model_catalog_api.py
git commit -m "feat(model-catalog): endpoints de características (get + refresh) e wiring"
```

---

## Frontend

### Task 9: Estender `Tooltip.tsx` (gatilho customizado + conteúdo rico)

**Files:**
- Modify: `frontend/components/ui/Tooltip.tsx`
- Modify: `frontend/tests/components/Tooltip.test.tsx`

**Interfaces:**
- Produces: `TooltipProps.trigger?: React.ReactElement`, `TooltipProps.renderContent?: () => React.ReactNode` (ambos opcionais, sem quebrar os usos existentes que só passam `content: string`).

- [ ] **Step 1: Escrever os testes novos (adicionar ao final de `tests/components/Tooltip.test.tsx`)**

```tsx
it("usa o elemento de trigger customizado em vez do botão '?' quando fornecido", async () => {
  const user = userEvent.setup();
  render(
    <Tooltip
      content="Painel de características"
      trigger={<div data-testid="card-customizado">Meu Card</div>}
      renderContent={() => <span>Conteúdo rico</span>}
    />,
  );

  expect(screen.queryByRole("button", { name: /Dica:/i })).not.toBeInTheDocument();
  const card = screen.getByTestId("card-customizado");

  await user.hover(card);
  expect(screen.getByRole("tooltip")).toHaveTextContent("Conteúdo rico");

  await user.unhover(card);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

it("preserva os handlers de hover já existentes no elemento de trigger", async () => {
  const user = userEvent.setup();
  const onMouseEnter = vi.fn();
  render(
    <Tooltip
      content="x"
      trigger={
        <div data-testid="card" onMouseEnter={onMouseEnter}>
          Card
        </div>
      }
      renderContent={() => <span>Conteúdo</span>}
    />,
  );

  await user.hover(screen.getByTestId("card"));

  expect(onMouseEnter).toHaveBeenCalled();
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
});
```

Confirme que `vi` já está importado em `tests/components/Tooltip.test.tsx` (se não estiver, adicione `vi` ao import de `"vitest"` no topo do arquivo).

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/components/Tooltip.test.tsx`
Expected: FAIL (o botão "?" ainda aparece mesmo com `trigger` passado, `renderContent` ignorado)

- [ ] **Step 3: Reescrever `frontend/components/ui/Tooltip.tsx`**

```tsx
"use client";

import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

// Detecta "estamos no cliente" sem `useState`+`useEffect` — useSyncExternalStore
// é o jeito recomendado pelo React para esse caso específico (retorna o
// snapshot do servidor até hidratar, depois o do cliente, sem o setState
// síncrono dentro de efeito que o hook set-state-in-effect reclamaria).
function subscribeNoop() {
  return () => {};
}
function useEstaNoCliente(): boolean {
  return useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
}

export type TooltipPosition = "top" | "bottom" | "left" | "right" | "auto";
export type TooltipAlign = "start" | "center" | "end" | "auto";

export interface TooltipProps {
  content: string;
  ariaLabel?: string;
  position?: TooltipPosition;
  align?: TooltipAlign;
  /** Elemento customizado que dispara o tooltip no hover/foco, no lugar do
   * botão "?" padrão — usado quando o gatilho precisa ser um elemento que
   * já tem seus próprios filhos interativos (ex.: um card inteiro com
   * botões dentro, que não podem ficar aninhados num <button>). Os
   * handlers de hover/foco já existentes no elemento passado continuam
   * sendo chamados (não são sobrescritos). */
  trigger?: ReactElement;
  /** Conteúdo rico (JSX) do corpo do tooltip, no lugar do texto simples de
   * `content`. `content` continua sendo usado para o `aria-label` padrão
   * do botão "?" quando `trigger` não é usado. */
  renderContent?: () => ReactNode;
}

/**
 * Componente de Tooltip acessível e inteligente para formulários, modais e
 * cards administrativos. Utiliza Portal do React e posicionamento fixo
 * dinâmico para garantir que o tooltip NUNCA seja cortado por contêineres
 * com scroll (`overflow-y-auto`) ou bordas de modais, ajustando seu
 * alinhamento à esquerda/direita.
 */
export function Tooltip({
  content,
  ariaLabel,
  position = "auto",
  align = "auto",
  trigger,
  renderContent,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const mounted = useEstaNoCliente();
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const tooltipWidth = renderContent ? 288 : 240; // w-72 vs w-60

  const updateCoords = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    // Em ambientes sem layout (como jsdom), rect pode retornar zeros
    if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) {
      setCoords(null);
      return;
    }

    const tooltipEstimatedHeight = 110;
    const viewportWidth = window.innerWidth || 1024;
    const viewportHeight = window.innerHeight || 768;

    let left = rect.left;

    if (align === "center") {
      left = rect.left + rect.width / 2 - tooltipWidth / 2;
    } else if (align === "end") {
      left = rect.right - tooltipWidth;
    } else if (align === "start") {
      left = rect.left;
    } else {
      // align === "auto"
      // Se o gatilho estiver próximo da borda esquerda, alinha à esquerda do gatilho
      if (rect.left < 200) {
        left = Math.max(16, rect.left - 4);
      } else if (rect.left > viewportWidth - tooltipWidth - 20) {
        // Se estiver próximo da borda direita, alinha à direita
        left = rect.right - tooltipWidth;
      } else {
        // Caso intermediário: levemente recuado à esquerda em relação ao gatilho
        left = rect.left - 16;
      }
    }

    // Limita estritamente dentro da viewport (com margem de 16px das bordas da tela)
    left = Math.max(16, Math.min(left, viewportWidth - tooltipWidth - 16));

    let top = rect.bottom + 6;
    if (
      position === "top" ||
      (position === "auto" && rect.bottom + tooltipEstimatedHeight > viewportHeight)
    ) {
      top = Math.max(12, rect.top - tooltipEstimatedHeight - 6);
    }

    setCoords({ top, left });
  }, [align, position, tooltipWidth]);

  useEffect(() => {
    if (isVisible) {
      updateCoords();
      window.addEventListener("scroll", updateCoords, true);
      window.addEventListener("resize", updateCoords);
      return () => {
        window.removeEventListener("scroll", updateCoords, true);
        window.removeEventListener("resize", updateCoords);
      };
    }
  }, [isVisible, updateCoords]);

  const tooltipBody = renderContent ? renderContent() : content;
  const classeCorpo = renderContent
    ? "w-72 rounded-xl border border-slate-200 bg-white p-3 text-xs font-normal leading-relaxed text-slate-900 shadow-2xl pointer-events-auto text-left animate-in fade-in-50 duration-150"
    : "w-60 rounded-xl border border-slate-700 bg-slate-900 p-2.5 text-xs font-normal leading-relaxed text-slate-100 shadow-2xl pointer-events-none text-left animate-in fade-in-50 duration-150";

  const tooltipElement = isVisible ? (
    <span
      ref={tooltipRef}
      role="tooltip"
      style={
        coords
          ? {
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
            }
          : undefined
      }
      className={coords ? `z-[9999] ${classeCorpo}` : `absolute top-full left-0 mt-1.5 z-[100] ${classeCorpo}`}
    >
      {tooltipBody}
    </span>
  ) : null;

  const tooltipPortal =
    mounted && typeof document !== "undefined"
      ? createPortal(tooltipElement, document.body)
      : tooltipElement;

  if (trigger) {
    const mostrar = () => setIsVisible(true);
    const esconder = () => setIsVisible(false);
    const triggerClonado = isValidElement(trigger)
      ? cloneElement(trigger, {
          ref: triggerRef,
          onMouseEnter: (e: React.MouseEvent) => {
            (trigger.props as { onMouseEnter?: (e: React.MouseEvent) => void }).onMouseEnter?.(e);
            mostrar();
          },
          onMouseLeave: (e: React.MouseEvent) => {
            (trigger.props as { onMouseLeave?: (e: React.MouseEvent) => void }).onMouseLeave?.(e);
            esconder();
          },
          onFocus: (e: React.FocusEvent) => {
            (trigger.props as { onFocus?: (e: React.FocusEvent) => void }).onFocus?.(e);
            mostrar();
          },
          onBlur: (e: React.FocusEvent) => {
            (trigger.props as { onBlur?: (e: React.FocusEvent) => void }).onBlur?.(e);
            esconder();
          },
        } as Partial<unknown>)
      : trigger;

    return (
      <>
        {triggerClonado}
        {tooltipPortal}
      </>
    );
  }

  return (
    <span className="relative inline-flex items-center">
      <button
        ref={triggerRef as React.RefObject<HTMLButtonElement>}
        type="button"
        onClick={() => setIsVisible((prev) => !prev)}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        aria-label={ariaLabel || `Dica: ${content}`}
        className="ml-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-200/80 text-[10px] font-bold text-slate-600 transition-all hover:bg-blue-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        ?
      </button>
      {tooltipPortal}
    </span>
  );
}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/components/Tooltip.test.tsx`
Expected: PASS (todos, incluindo os 3 testes originais — comportamento default intacto)

- [ ] **Step 5: `tsc` e `prettier`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check components/ui/Tooltip.tsx tests/components/Tooltip.test.tsx
```

Corrija qualquer erro de tipo (o cast `as Partial<unknown>` no `cloneElement` é deliberado — `trigger` é tipado como `ReactElement` genérico de propósito, para aceitar qualquer `<div>`/card sem exigir um tipo de props específico).

- [ ] **Step 6: Commit**

```bash
git add frontend/components/ui/Tooltip.tsx frontend/tests/components/Tooltip.test.tsx
git commit -m "feat(ui): Tooltip aceita trigger customizado e conteúdo rico"
```

---

### Task 10: Tipos e cliente HTTP (`lib/types/modelCatalog.ts`, `lib/api/modelCatalog.ts`)

**Files:**
- Create: `frontend/lib/types/modelCatalog.ts`
- Create: `frontend/lib/api/modelCatalog.ts`
- Test: `frontend/tests/lib/api/modelCatalog.test.ts`

**Interfaces:**
- Produces: `ModelSource`, `ModelCharacteristics` (types); `ModelCatalogApiError`, `getModelCharacteristics(source, tag) -> Promise<ModelCharacteristics | null>`, `refreshModelCharacteristics(source, tag) -> Promise<ModelCharacteristics | null>`.

- [ ] **Step 1: Criar `frontend/lib/types/modelCatalog.ts`**

```typescript
/**
 * Tipos do contrato dos endpoints de características de modelo (ver
 * `backend/src/app/models/model_catalog.py` e
 * docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md).
 */

export type ModelSource = "openrouter" | "ollama" | "huggingface";

/** Resposta de `GET/POST .../model-catalog/characteristics`. */
export interface ModelCharacteristics {
  source: ModelSource;
  tag: string;
  is_multimodal: boolean;
  input_modalities: string[];
  output_modalities: string[];
  context_length: number | null;
  parameter_size: string | null;
  quantization: string | null;
  pricing_prompt_per_1k: number | null;
  pricing_completion_per_1k: number | null;
  knowledge_cutoff: string | null;
  fetched_at: string;
}
```

- [ ] **Step 2: Escrever o teste do cliente HTTP**

```typescript
// frontend/tests/lib/api/modelCatalog.test.ts
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ModelCatalogApiError,
  getModelCharacteristics,
  refreshModelCharacteristics,
} from "@/lib/api/modelCatalog";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

const CARACTERISTICAS_EXEMPLO = {
  source: "openrouter",
  tag: "openai/gpt-4o-mini",
  is_multimodal: true,
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  parameter_size: null,
  quantization: null,
  pricing_prompt_per_1k: 0.00015,
  pricing_completion_per_1k: 0.0006,
  knowledge_cutoff: "2023-10-31",
  fetched_at: "2026-10-03T12:00:00Z",
};

describe("getModelCharacteristics", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("devolve as características quando a resposta é 200", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(CARACTERISTICAS_EXEMPLO, 200)));

    const resultado = await getModelCharacteristics("openrouter", "openai/gpt-4o-mini");

    expect(resultado).toEqual(CARACTERISTICAS_EXEMPLO);
  });

  it("devolve null quando a resposta é 404 (sem característica pra essa tag)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "não achado" }, 404)));

    const resultado = await getModelCharacteristics("openrouter", "tag/inexistente");

    expect(resultado).toBeNull();
  });

  it("lança ModelCatalogApiError em erro 500", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    await expect(getModelCharacteristics("openrouter", "x")).rejects.toBeInstanceOf(
      ModelCatalogApiError,
    );
  });
});

describe("refreshModelCharacteristics", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("faz POST para o endpoint de refresh e devolve as características atualizadas", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(CARACTERISTICAS_EXEMPLO, 200));
    vi.stubGlobal("fetch", mockFetch);

    const resultado = await refreshModelCharacteristics("openrouter", "openai/gpt-4o-mini");

    expect(resultado).toEqual(CARACTERISTICAS_EXEMPLO);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/characteristics/refresh"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
```

- [ ] **Step 3: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/lib/api/modelCatalog.test.ts`
Expected: FAIL (módulo `@/lib/api/modelCatalog` não existe)

- [ ] **Step 4: Criar `frontend/lib/api/modelCatalog.ts`**

```typescript
import type { ModelCharacteristics, ModelSource } from "@/lib/types/modelCatalog";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

/** Erro de comunicação com os endpoints de características de modelo. */
export class ModelCatalogApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ModelCatalogApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  throw new ModelCatalogApiError(detail ?? mensagemPadrao, response.status);
}

/**
 * Busca as características cacheadas (ou recém-buscadas) de um modelo via
 * `GET /api/admin/model-catalog/characteristics`. `null` quando a fonte não
 * tem característica pra essa tag (404) — não é um erro.
 */
export async function getModelCharacteristics(
  source: ModelSource,
  tag: string,
): Promise<ModelCharacteristics | null> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/admin/model-catalog/characteristics?source=${encodeURIComponent(
        source,
      )}&tag=${encodeURIComponent(tag)}`,
    );
  } catch {
    throw new ModelCatalogApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (response.status === 404) return null;
  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível obter as características do modelo.");
  }

  return (await response.json()) as ModelCharacteristics;
}

/** Força nova busca na fonte via `POST .../characteristics/refresh`, ignorando o cache. */
export async function refreshModelCharacteristics(
  source: ModelSource,
  tag: string,
): Promise<ModelCharacteristics | null> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/model-catalog/characteristics/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, tag }),
    });
  } catch {
    throw new ModelCatalogApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (response.status === 404) return null;
  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível atualizar as características do modelo.");
  }

  return (await response.json()) as ModelCharacteristics;
}
```

- [ ] **Step 5: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/lib/api/modelCatalog.test.ts`
Expected: PASS (4 testes)

- [ ] **Step 6: `tsc`/`prettier`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check lib/types/modelCatalog.ts lib/api/modelCatalog.ts tests/lib/api/modelCatalog.test.ts
```

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/types/modelCatalog.ts frontend/lib/api/modelCatalog.ts frontend/tests/lib/api/modelCatalog.test.ts
git commit -m "feat(model-catalog): tipos e cliente HTTP do frontend"
```

---

### Task 11: Hook `useModelCharacteristics`

**Files:**
- Create: `frontend/lib/hooks/useModelCharacteristics.ts`
- Test: `frontend/tests/lib/hooks/useModelCharacteristics.test.ts`

**Interfaces:**
- Consumes: `getModelCharacteristics`, `refreshModelCharacteristics`, `ModelCatalogApiError` (Task 10).
- Produces: `useModelCharacteristics(source: ModelSource, tag: string) -> { data: ModelCharacteristics | null; loading: boolean; error: string | null; refresh: () => Promise<void> }`.

- [ ] **Step 1: Escrever o teste**

```typescript
// frontend/tests/lib/hooks/useModelCharacteristics.test.ts
import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";

vi.mock("@/lib/api/modelCatalog", () => ({
  getModelCharacteristics: vi.fn(),
  refreshModelCharacteristics: vi.fn(),
  ModelCatalogApiError: class extends Error {},
}));

import {
  getModelCharacteristics,
  refreshModelCharacteristics,
} from "@/lib/api/modelCatalog";

const mockGet = vi.mocked(getModelCharacteristics);
const mockRefresh = vi.mocked(refreshModelCharacteristics);

const CARACTERISTICAS = {
  source: "openrouter" as const,
  tag: "openai/gpt-4o-mini",
  is_multimodal: true,
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  parameter_size: null,
  quantization: null,
  pricing_prompt_per_1k: 0.00015,
  pricing_completion_per_1k: 0.0006,
  knowledge_cutoff: "2023-10-31",
  fetched_at: "2026-10-03T12:00:00Z",
};

describe("useModelCharacteristics", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("busca no mount e expõe o resultado", async () => {
    mockGet.mockResolvedValue(CARACTERISTICAS);

    const { result } = renderHook(() => useModelCharacteristics("openrouter", "openai/gpt-4o-mini"));

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(CARACTERISTICAS);
    expect(mockGet).toHaveBeenCalledWith("openrouter", "openai/gpt-4o-mini");
  });

  it("não refaz a busca para a mesma tag já cacheada", async () => {
    mockGet.mockResolvedValue(CARACTERISTICAS);

    const { unmount } = renderHook(() =>
      useModelCharacteristics("openrouter", "openai/gpt-4o-mini"),
    );
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    unmount();

    renderHook(() => useModelCharacteristics("openrouter", "openai/gpt-4o-mini"));

    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("refresh() chama o endpoint de refresh e atualiza o estado", async () => {
    mockGet.mockResolvedValue(null);
    mockRefresh.mockResolvedValue(CARACTERISTICAS);

    const { result } = renderHook(() =>
      useModelCharacteristics("openrouter", "modelo-ainda-nao-cacheado"),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockRefresh).toHaveBeenCalledWith("openrouter", "modelo-ainda-nao-cacheado");
    expect(result.current.data).toEqual(CARACTERISTICAS);
  });
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/lib/hooks/useModelCharacteristics.test.ts`
Expected: FAIL (módulo não existe)

- [ ] **Step 3: Criar `frontend/lib/hooks/useModelCharacteristics.ts`**

```typescript
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ModelCatalogApiError,
  getModelCharacteristics,
  refreshModelCharacteristics,
} from "@/lib/api/modelCatalog";
import type { ModelCharacteristics, ModelSource } from "@/lib/types/modelCatalog";

// Cache em memória da aba (sobrevive entre cards diferentes que pedem a
// mesma tag, não entre reloads) — ver
// docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md §4.3.
const _cache = new Map<string, ModelCharacteristics | null>();

function chaveCache(source: ModelSource, tag: string): string {
  return `${source}:${tag}`;
}

export interface UseModelCharacteristicsResult {
  /** `null` com `loading=false` e `error=null` significa "fonte não tem
   * característica pra essa tag" (404), não um erro. */
  data: ModelCharacteristics | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useModelCharacteristics(
  source: ModelSource,
  tag: string,
): UseModelCharacteristicsResult {
  const chave = chaveCache(source, tag);
  const [data, setData] = useState<ModelCharacteristics | null>(() => _cache.get(chave) ?? null);
  const [loading, setLoading] = useState(!_cache.has(chave));
  const [error, setError] = useState<string | null>(null);
  const montadoRef = useRef(true);

  useEffect(() => {
    montadoRef.current = true;
    return () => {
      montadoRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (_cache.has(chave)) {
      setData(_cache.get(chave) ?? null);
      setLoading(false);
      return;
    }

    let cancelado = false;
    setLoading(true);
    setError(null);

    getModelCharacteristics(source, tag)
      .then((resultado) => {
        if (cancelado) return;
        _cache.set(chave, resultado);
        setData(resultado);
      })
      .catch((err) => {
        if (cancelado) return;
        setError(
          err instanceof ModelCatalogApiError ? err.message : "Erro ao buscar características.",
        );
      })
      .finally(() => {
        if (!cancelado) setLoading(false);
      });

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resultado = await refreshModelCharacteristics(source, tag);
      if (!montadoRef.current) return;
      _cache.set(chave, resultado);
      setData(resultado);
    } catch (err) {
      if (!montadoRef.current) return;
      setError(
        err instanceof ModelCatalogApiError ? err.message : "Erro ao atualizar características.",
      );
    } finally {
      if (montadoRef.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chave]);

  return { data, loading, error, refresh };
}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/lib/hooks/useModelCharacteristics.test.ts`
Expected: PASS (3 testes)

- [ ] **Step 5: `tsc`/`prettier`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check lib/hooks/useModelCharacteristics.ts tests/lib/hooks/useModelCharacteristics.test.ts
```

- [ ] **Step 6: Commit**

```bash
git add frontend/lib/hooks/useModelCharacteristics.ts frontend/tests/lib/hooks/useModelCharacteristics.test.ts
git commit -m "feat(model-catalog): hook useModelCharacteristics com cache por aba"
```

---

### Task 12: `ModelCharacteristicsPanel` (componente de apresentação)

**Files:**
- Create: `frontend/components/admin/ModelCharacteristicsPanel.tsx`
- Test: `frontend/tests/components/ModelCharacteristicsPanel.test.tsx`

**Interfaces:**
- Consumes: `ModelCharacteristics` (Task 10).
- Produces: `ModelCharacteristicsPanel({ data, loading, error, onRefresh }) -> JSX`.

- [ ] **Step 1: Escrever o teste**

```tsx
// frontend/tests/components/ModelCharacteristicsPanel.test.tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";

const CARACTERISTICAS = {
  source: "openrouter" as const,
  tag: "openai/gpt-4o-mini",
  is_multimodal: true,
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  parameter_size: null,
  quantization: null,
  pricing_prompt_per_1k: 0.00015,
  pricing_completion_per_1k: 0.0006,
  knowledge_cutoff: "2023-10-31",
  fetched_at: new Date().toISOString(),
};

describe("ModelCharacteristicsPanel", () => {
  it("mostra as modalidades de entrada e saída explicitamente (não um badge binário)", () => {
    render(
      <ModelCharacteristicsPanel data={CARACTERISTICAS} loading={false} error={null} onRefresh={vi.fn()} />,
    );

    expect(screen.getByText("Texto")).toBeInTheDocument();
    expect(screen.getByText("Imagem")).toBeInTheDocument();
    expect(screen.queryByText(/multimodal/i)).not.toBeInTheDocument();
  });

  it("mostra contexto formatado em K tokens", () => {
    render(
      <ModelCharacteristicsPanel data={CARACTERISTICAS} loading={false} error={null} onRefresh={vi.fn()} />,
    );

    expect(screen.getByText(/128K tokens/)).toBeInTheDocument();
  });

  it("mostra texto de carregamento quando loading e sem dado ainda", () => {
    render(<ModelCharacteristicsPanel data={null} loading={true} error={null} onRefresh={vi.fn()} />);

    expect(screen.getByText(/Carregando características/i)).toBeInTheDocument();
  });

  it("mostra mensagem discreta quando não há dado nem erro (404)", () => {
    render(<ModelCharacteristicsPanel data={null} loading={false} error={null} onRefresh={vi.fn()} />);

    expect(screen.getByText(/indisponíveis no momento/i)).toBeInTheDocument();
  });

  it("chama onRefresh ao clicar no botão de atualizar", () => {
    const onRefresh = vi.fn();
    render(
      <ModelCharacteristicsPanel data={CARACTERISTICAS} loading={false} error={null} onRefresh={onRefresh} />,
    );

    fireEvent.click(screen.getByLabelText("Atualizar características"));

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/components/ModelCharacteristicsPanel.test.tsx`
Expected: FAIL (módulo não existe)

- [ ] **Step 3: Criar `frontend/components/admin/ModelCharacteristicsPanel.tsx`**

```tsx
"use client";

import type { ModelCharacteristics } from "@/lib/types/modelCatalog";

const NOMES_MODALIDADE: Record<string, string> = {
  text: "Texto",
  image: "Imagem",
  audio: "Áudio",
  video: "Vídeo",
  file: "Arquivo",
  desconhecido: "Desconhecido",
};

const MODALIDADES_NAO_TEXTO = new Set(["image", "audio", "video"]);

function Chip({ modalidade }: { modalidade: string }) {
  const destaque = MODALIDADES_NAO_TEXTO.has(modalidade);
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
        destaque ? "bg-blue-100 text-blue-800" : "bg-slate-100 text-slate-600"
      }`}
    >
      {NOMES_MODALIDADE[modalidade] ?? modalidade}
    </span>
  );
}

function formatarContexto(contextLength: number | null): string | null {
  if (contextLength === null) return null;
  if (contextLength >= 1000) return `${Math.round(contextLength / 1000)}K tokens`;
  return `${contextLength} tokens`;
}

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffHoras = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHoras < 1) return "agora há pouco";
  if (diffHoras < 24) return `há ${diffHoras}h`;
  return `há ${Math.floor(diffHoras / 24)}d`;
}

export interface ModelCharacteristicsPanelProps {
  data: ModelCharacteristics | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function ModelCharacteristicsPanel({
  data,
  loading,
  error,
  onRefresh,
}: ModelCharacteristicsPanelProps) {
  if (loading && !data) {
    return <div className="text-[11px] text-slate-500 italic">Carregando características...</div>;
  }

  if (!data) {
    return (
      <div className="text-[11px] text-slate-500 italic">
        {error ?? "Características indisponíveis no momento."}
      </div>
    );
  }

  const contexto = formatarContexto(data.context_length);

  return (
    <div className="space-y-1.5 text-left">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Entrada
        </span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRefresh();
          }}
          disabled={loading}
          aria-label="Atualizar características"
          className="text-slate-400 hover:text-blue-600 disabled:opacity-40 cursor-pointer"
        >
          {loading ? "⏳" : "⟳"}
        </button>
      </div>
      <div className="flex flex-wrap gap-1">
        {data.input_modalities.map((m) => (
          <Chip key={m} modalidade={m} />
        ))}
      </div>

      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
        Saída
      </span>
      <div className="flex flex-wrap gap-1">
        {data.output_modalities.map((m) => (
          <Chip key={m} modalidade={m} />
        ))}
      </div>

      {contexto && <p className="text-[11px] text-slate-600">Contexto: {contexto}</p>}
      {data.parameter_size && (
        <p className="text-[11px] text-slate-600">Parâmetros: {data.parameter_size}</p>
      )}
      {data.quantization && (
        <p className="text-[11px] text-slate-600">Quantização: {data.quantization}</p>
      )}
      {data.pricing_prompt_per_1k !== null && (
        <p className="text-[11px] text-slate-600">
          Preço: ${data.pricing_prompt_per_1k.toFixed(5)}/1K entrada · $
          {data.pricing_completion_per_1k?.toFixed(5)}/1K saída
        </p>
      )}
      {data.knowledge_cutoff && (
        <p className="text-[11px] text-slate-600">Dados até: {data.knowledge_cutoff}</p>
      )}
      <p className="text-[10px] text-slate-400">Atualizado {formatarDataRelativa(data.fetched_at)}</p>
    </div>
  );
}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/components/ModelCharacteristicsPanel.test.tsx`
Expected: PASS (5 testes)

- [ ] **Step 5: `tsc`/`prettier`/`eslint`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check components/admin/ModelCharacteristicsPanel.tsx tests/components/ModelCharacteristicsPanel.test.tsx
npx eslint components/admin/ModelCharacteristicsPanel.tsx
```

- [ ] **Step 6: Commit**

```bash
git add frontend/components/admin/ModelCharacteristicsPanel.tsx frontend/tests/components/ModelCharacteristicsPanel.test.tsx
git commit -m "feat(model-catalog): componente ModelCharacteristicsPanel"
```

---

### Task 13: Integrar em `OpenRouterModelCard.tsx`

**Files:**
- Modify: `frontend/components/admin/OpenRouterModelCard.tsx`
- Modify: `frontend/tests/components/OpenRouterModelCard.test.tsx`

**Interfaces:**
- Consumes: `Tooltip` (Task 9), `useModelCharacteristics` (Task 11), `ModelCharacteristicsPanel` (Task 12).

- [ ] **Step 1: Escrever o teste novo (adicionar ao arquivo existente)**

Adicione o mock do hook no topo do arquivo de teste (junto do mock de `@/lib/api/runtimeSettings` já existente):

```tsx
vi.mock("@/lib/hooks/useModelCharacteristics", () => ({
  useModelCharacteristics: vi.fn(() => ({
    data: {
      source: "openrouter",
      tag: "openai/gpt-4o-mini",
      is_multimodal: true,
      input_modalities: ["text", "image"],
      output_modalities: ["text"],
      context_length: 128000,
      parameter_size: null,
      quantization: null,
      pricing_prompt_per_1k: 0.00015,
      pricing_completion_per_1k: 0.0006,
      knowledge_cutoff: "2023-10-31",
      fetched_at: new Date().toISOString(),
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  })),
}));
```

E o teste:

```tsx
it("mostra as características do modelo ao passar o mouse sobre o card", async () => {
  const user = userEvent.setup();
  render(<OpenRouterModelCard onError={vi.fn()} onSuccess={vi.fn()} />);

  await waitFor(() => {
    expect(screen.getAllByText("openai/gpt-4o-mini").length).toBeGreaterThan(0);
  });

  const cardGptMini = screen.getByText("GPT-4o Mini").closest("div")!;
  await user.hover(cardGptMini);

  expect(await screen.findByText("Imagem")).toBeInTheDocument();
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/components/OpenRouterModelCard.test.tsx`
Expected: FAIL (o hover não mostra nada ainda — o card não está envolvido em `Tooltip`)

- [ ] **Step 3: Modificar `frontend/components/admin/OpenRouterModelCard.tsx`**

Adicione os imports no topo:

```tsx
import { Tooltip } from "@/components/ui/Tooltip";
import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";
```

Crie um pequeno componente interno (antes de `export function OpenRouterModelCard`) para não repetir a chamada do hook em cada `.map`:

```tsx
function CardComCaracteristicas({ tag, children }: { tag: string; children: React.ReactElement }) {
  const { data, loading, error, refresh } = useModelCharacteristics("openrouter", tag);
  return (
    <Tooltip
      content={`Características de ${tag}`}
      trigger={children}
      renderContent={() => (
        <ModelCharacteristicsPanel data={data} loading={loading} error={error} onRefresh={refresh} />
      )}
    />
  );
}
```

Em cada um dos três `.map` (`POPULAR_MODELS`, `FREE_MODELS`, `historyModels`), envolva o `<div key={...}>` existente com `<CardComCaracteristicas tag={...}>...</CardComCaracteristicas>`, movendo a `key` para o componente externo. Por exemplo, no grid de `POPULAR_MODELS` (e de forma análoga nos outros dois grids):

```tsx
{POPULAR_MODELS.map((model) => {
  const isSelected = activeModel === model.tag;
  const isActivating = activatingTag === model.tag;

  return (
    <CardComCaracteristicas key={model.tag} tag={model.tag}>
      <div
        className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
          isSelected
            ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
            : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
        }`}
      >
        {/* ...conteúdo do card exatamente como já está, sem mudanças... */}
      </div>
    </CardComCaracteristicas>
  );
})}
```

Repita o mesmo padrão (mover `key` para `CardComCaracteristicas`, manter o `<div>` interno idêntico) nos grids de `FREE_MODELS` e `historyModels` — para o de `historyModels`, use `tag` (a própria string) tanto como `key`/`tag` do `CardComCaracteristicas` quanto como conteúdo.

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/components/OpenRouterModelCard.test.tsx`
Expected: PASS (todos, incluindo os testes já existentes e o novo)

- [ ] **Step 5: `tsc`/`prettier`/`eslint`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check components/admin/OpenRouterModelCard.tsx tests/components/OpenRouterModelCard.test.tsx
npx eslint components/admin/OpenRouterModelCard.tsx
```

- [ ] **Step 6: Commit**

```bash
git add frontend/components/admin/OpenRouterModelCard.tsx frontend/tests/components/OpenRouterModelCard.test.tsx
git commit -m "feat(model-catalog): hover com características nos cards do OpenRouter"
```

---

### Task 14: Integrar em `LocalModelsTable.tsx`

**Files:**
- Modify: `frontend/components/admin/LocalModelsTable.tsx`
- Modify: `frontend/tests/components/LocalModelsTable.test.tsx`

**Interfaces:**
- Consumes: `Tooltip`, `useModelCharacteristics`, `ModelCharacteristicsPanel` (mesmos de Task 13, `source="ollama"`).

- [ ] **Step 1: Escrever o teste novo**

Primeiro confira como o arquivo de teste já monta `models: LocalModel[]` (`grep -n "models:" frontend/tests/components/LocalModelsTable.test.tsx`) para reaproveitar o mesmo formato. Adicione o mock do hook (mesmo formato da Task 13) e:

```tsx
it("mostra as características ao passar o mouse sobre um modelo instalado", async () => {
  const user = userEvent.setup();
  render(
    <LocalModelsTable
      models={[
        { name: "qwen2.5:7b", size_bytes: 4_700_000_000, modified_at: new Date().toISOString(), is_active: true },
      ]}
      onChanged={vi.fn()}
      onError={vi.fn()}
      onSuccess={vi.fn()}
    />,
  );

  const card = screen.getByText("qwen2.5:7b").closest("div")!;
  await user.hover(card);

  expect(await screen.findByText("Imagem")).toBeInTheDocument();
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/components/LocalModelsTable.test.tsx`
Expected: FAIL

- [ ] **Step 3: Modificar `frontend/components/admin/LocalModelsTable.tsx`**

Mesmo padrão da Task 13: importar `Tooltip`, `ModelCharacteristicsPanel`, `useModelCharacteristics`; criar:

```tsx
function CardComCaracteristicas({ tag, children }: { tag: string; children: React.ReactElement }) {
  const { data, loading, error, refresh } = useModelCharacteristics("ollama", tag);
  return (
    <Tooltip
      content={`Características de ${tag}`}
      trigger={children}
      renderContent={() => (
        <ModelCharacteristicsPanel data={data} loading={loading} error={error} onRefresh={refresh} />
      )}
    />
  );
}
```

Envolver os dois grids (`models.map` dos instalados, usando `tag={modelo.name}`, e `POPULAR_LOCAL_PRESETS.map`, usando `tag={preset.tag}`) da mesma forma — mover a `key` existente para `CardComCaracteristicas`, manter o `<div>` interno de cada card idêntico ao que já existe.

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/components/LocalModelsTable.test.tsx`
Expected: PASS (todos)

- [ ] **Step 5: `tsc`/`prettier`/`eslint`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check components/admin/LocalModelsTable.tsx tests/components/LocalModelsTable.test.tsx
npx eslint components/admin/LocalModelsTable.tsx
```

- [ ] **Step 6: Commit**

```bash
git add frontend/components/admin/LocalModelsTable.tsx frontend/tests/components/LocalModelsTable.test.tsx
git commit -m "feat(model-catalog): hover com características nos cards do Ollama local"
```

---

### Task 15: Preview no `PullModelForm.tsx` para tags `hf.co/...`

**Files:**
- Modify: `frontend/components/admin/PullModelForm.tsx`
- Modify: `frontend/tests/components/PullModelForm.test.tsx`

**Interfaces:**
- Consumes: `ModelCharacteristicsPanel` (Task 12), `getModelCharacteristics`/`refreshModelCharacteristics` (Task 10) — **não** usa `Tooltip`/hover aqui (painel inline, sempre visível quando a condição bate).

- [ ] **Step 1: Escrever o teste**

```tsx
// adicionar ao final de frontend/tests/components/PullModelForm.test.tsx
vi.mock("@/lib/api/modelCatalog", () => ({
  getModelCharacteristics: vi.fn(),
  refreshModelCharacteristics: vi.fn(),
  ModelCatalogApiError: class extends Error {},
}));

import { getModelCharacteristics } from "@/lib/api/modelCatalog";

describe("preview de características para tags do Hugging Face", () => {
  it("mostra o preview 500ms depois de digitar uma tag hf.co/...", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    vi.mocked(getModelCharacteristics).mockResolvedValue({
      source: "huggingface",
      tag: "hf.co/Qwen/Qwen2.5-VL-7B-Instruct",
      is_multimodal: true,
      input_modalities: ["text", "image"],
      output_modalities: ["text"],
      context_length: null,
      parameter_size: null,
      quantization: null,
      pricing_prompt_per_1k: null,
      pricing_completion_per_1k: null,
      knowledge_cutoff: null,
      fetched_at: new Date().toISOString(),
    });

    render(<PullModelForm onPulled={vi.fn()} />);
    await user.type(
      screen.getByLabelText(/Nome do modelo/i),
      "hf.co/Qwen/Qwen2.5-VL-7B-Instruct",
    );

    vi.advanceTimersByTime(500);
    expect(await screen.findByText("Imagem")).toBeInTheDocument();

    vi.useRealTimers();
  });

  it("não mostra preview para tags que não são hf.co/...", async () => {
    vi.useFakeTimers();
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<PullModelForm onPulled={vi.fn()} />);
    await user.type(screen.getByLabelText(/Nome do modelo/i), "llama3.1:8b");

    vi.advanceTimersByTime(500);
    expect(getModelCharacteristics).not.toHaveBeenCalled();

    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: Rodar e confirmar falha**

Run: `cd frontend && npx vitest run tests/components/PullModelForm.test.tsx -t "Hugging Face"`
Expected: FAIL (nenhum preview é mostrado ainda)

- [ ] **Step 3: Modificar `frontend/components/admin/PullModelForm.tsx`**

Adicione os imports no topo:

```tsx
import { getModelCharacteristics } from "@/lib/api/modelCatalog";
import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import type { ModelCharacteristics } from "@/lib/types/modelCatalog";
```

Dentro de `PullModelForm`, adicione o estado e o efeito de debounce (perto dos outros `useState`/`useEffect` já existentes):

```tsx
const [previewHf, setPreviewHf] = useState<ModelCharacteristics | null>(null);
const [previewHfLoading, setPreviewHfLoading] = useState(false);
const [previewHfError, setPreviewHfError] = useState<string | null>(null);

useEffect(() => {
  if (!/^hf\.co\//i.test(nome.trim())) {
    setPreviewHf(null);
    setPreviewHfError(null);
    return;
  }

  const tagAtual = nome.trim();
  setPreviewHfLoading(true);
  const timeoutId = setTimeout(() => {
    getModelCharacteristics("huggingface", tagAtual)
      .then((resultado) => {
        setPreviewHf(resultado);
        setPreviewHfError(null);
      })
      .catch(() => {
        setPreviewHfError("Não foi possível obter características deste repositório.");
      })
      .finally(() => setPreviewHfLoading(false));
  }, 500);

  return () => clearTimeout(timeoutId);
}, [nome]);

const handleRefreshPreview = () => {
  // refresh manual do preview antes de baixar — reaproveita o mesmo
  // endpoint usado pelo painel pós-download (ver ModelCharacteristicsPanel)
  setPreviewHfLoading(true);
  import("@/lib/api/modelCatalog").then(({ refreshModelCharacteristics }) =>
    refreshModelCharacteristics("huggingface", nome.trim())
      .then((resultado) => setPreviewHf(resultado))
      .finally(() => setPreviewHfLoading(false)),
  );
};
```

Adicione o painel no JSX, logo depois do bloco de "Sugestões rápidas" (antes do bloco `{progresso && ...}`):

```tsx
{/^hf\.co\//i.test(nome.trim()) && (
  <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
    <ModelCharacteristicsPanel
      data={previewHf}
      loading={previewHfLoading}
      error={previewHfError}
      onRefresh={handleRefreshPreview}
    />
  </div>
)}
```

- [ ] **Step 4: Rodar e confirmar sucesso**

Run: `cd frontend && npx vitest run tests/components/PullModelForm.test.tsx`
Expected: PASS (todos, incluindo os testes já existentes)

- [ ] **Step 5: `tsc`/`prettier`/`eslint`**

```bash
cd frontend && npx tsc --noEmit
npx prettier --check components/admin/PullModelForm.tsx tests/components/PullModelForm.test.tsx
npx eslint components/admin/PullModelForm.tsx
```

- [ ] **Step 6: Commit**

```bash
git add frontend/components/admin/PullModelForm.tsx frontend/tests/components/PullModelForm.test.tsx
git commit -m "feat(model-catalog): preview de características para tags hf.co/... antes de baixar"
```

---

### Task 16: Verificação manual end-to-end + documentação

**Files:**
- Modify: `docs/ARCHITECTURE.md`
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Subir backend e frontend reais**

```bash
cd backend && .venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 &
cd frontend && npm run dev &
sleep 5
```

- [ ] **Step 2: Testar manualmente no navegador**

Abra `http://localhost:3001/admin/modelos` (ajuste a porta conforme `docs/FRONTEND.md` se for diferente). Confira:
- Hover num card de "Modelos Populares no OpenRouter" (ex.: GPT-4o Mini) mostra painel com chips "Texto"/"Imagem" em Entrada, "Texto" em Saída, contexto, preço.
- Hover num card instalado em "Modelos Locais Instalados" mostra o painel (modelo só-texto → só chip "Texto").
- Clicar no ícone de refresh (⟳) dentro do painel atualiza e mostra "Atualizado agora há pouco".
- Em "Baixar modelo", digitar `hf.co/Qwen/Qwen2.5-VL-7B-Instruct` mostra o preview com "Imagem" depois de ~500ms; digitar `llama3.1:8b` não mostra preview nenhum.

- [ ] **Step 3: Encerrar os processos**

```bash
kill %1 %2
```

- [ ] **Step 4: Atualizar `docs/ARCHITECTURE.md`**

Adicione uma nova entrada de "Decisão registrada" (seguindo o padrão das demais, com data de hoje) descrevendo: as três fontes de dados, a tabela `model_characteristics` com staleness de 7 dias e refresh manual, e a extensão do `Tooltip` para aceitar gatilho customizado. Referencie `docs/superpowers/specs/2026-10-03-caracteristicas-modelo-hover-design.md`.

- [ ] **Step 5: Atualizar `docs/ROADMAP.md`**

Adicione uma entrada `- [x]` sob "Extra fora do MVP" (mesmo padrão da entrada do gerenciador de modelos locais), resumindo a entrega e citando os arquivos de teste novos.

- [ ] **Step 6: Rodar as suítes completas (backend + frontend) uma última vez**

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx vitest run
cd frontend && npx tsc --noEmit
```

Expected: tudo PASS, zero erros de tipo.

- [ ] **Step 7: Commit final**

```bash
git add docs/ARCHITECTURE.md docs/ROADMAP.md
git commit -m "docs: registrar características de modelo no hover (ARCHITECTURE/ROADMAP)"
```

---

## Self-Review (preenchido durante a escrita deste plano)

**Cobertura da spec:** as 3 fontes (Tasks 4-6), a tabela/staleness/refresh (Tasks 1, 7, 8), o `Tooltip` estendido (Task 9), a integração nos dois grids + preview do Hugging Face no form de pull (Tasks 13-15), e o registro em ARCHITECTURE/ROADMAP (Task 16) — todas as seções da spec têm uma task correspondente. Os não-objetivos (sem busca navegável, sem busca por palavra-chave no HF) não geram tasks, como esperado.

**Consistência de tipos:** `ModelCharacteristics` (frontend) espelha `ModelCharacteristicsResponse` (backend) campo a campo; `ModelSource` idêntico nos dois lados; `useModelCharacteristics` devolve exatamente `{data, loading, error, refresh}` consumido igual nas Tasks 13-15; `ModelCharacteristicsPanelProps` consistente entre Task 12 (definição) e Tasks 13-15 (uso).
