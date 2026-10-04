# Contabilizador de Tokens Internos/Externos e Custos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement token accounting for internal (Ollama) and external (OpenRouter) models with input/output cost segregation, chat session closure lifecycle with background inactivity timeout, and the `/admin/metricas` reporting dashboard.

**Architecture:** Extend SQLAlchemy schema for conversation status (`status`, `encerrada_em`, `motivo_encerramento`) via Alembic migration `0018`. Enhance `OpenRouterClient` and `OllamaClient` to report segregated prompt and completion token costs in `LLMResponse`/`LLMStreamChunk` and store them in `conversa_mensagens.metricas`. Add chat closure REST endpoints, a background inactivity worker for 30-minute auto-closure, a metrics aggregation endpoint `GET /api/admin/metrics/tokens-and-costs`, and a Next.js `/admin/metricas` dashboard.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.0, AsyncPG / PostgreSQL, Pydantic v2, Alembic, Next.js 14 (App Router, TypeScript, Tailwind CSS, Lucide icons, Vitest, pytest).

**Spec:** [`docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md`](docs/superpowers/specs/2026-10-03-contabilizador-tokens-custos-design.md)

## Global Constraints

- Python backend: strict type annotations, async SQLAlchemy sessions, Pydantic v2 schemas.
- Database: Alembic migration for all schema changes, no raw SQL unless inside SQLAlchemy `text()` queries for aggregations.
- Frontend: Next.js App Router, Tailwind CSS, standard TypeScript interfaces, zero browser-default styled elements.
- Testing: All backend logic covered by `pytest`, all frontend components covered by `vitest`.

## Review Focus

- Input with missing token metrics from OpenRouter stream: system must fall back gracefully to 0 tokens / $0.00 cost without throwing exceptions.
- Chat closure idempotency: calling close endpoint on an already closed conversation must return the existing conversation state without error (HTTP 200).
- Inactivity worker timing boundary: active chats with messages younger than 30 minutes must not be closed by the background task.
- Date grouping edge case: daily metric queries spanning timezone boundaries must aggregate cleanly by `date(encerrada_em)`.
- Zero-token local model accounting: local model responses must report input and output tokens accurately with cost strictly equal to 0.00.

---

### Task 1: Database Migration for Conversation Status & Cost Metrics

**Files:**
- Create: `backend/migrations/versions/0018_conversas_status_custos.py`
- Modify: `backend/src/app/db/models.py:317-345`
- Test: `backend/tests/test_conversas_status_schema.py`

**Interfaces:**
- Consumes: `Conversa` model in `app.db.models`.
- Produces: `Conversa.status`, `Conversa.encerrada_em`, `Conversa.motivo_encerramento` fields.

- [ ] **Step 1: Write the failing test for model schema**

```python
import pytest
from app.db.models import Conversa
from datetime import datetime, UTC

def test_conversa_model_has_status_and_closure_fields():
    conversa = Conversa(
        id="test-session-123",
        status="encerrada",
        encerrada_em=datetime.now(UTC),
        motivo_encerramento="manual_usuario"
    )
    assert conversa.status == "encerrada"
    assert conversa.encerrada_em is not None
    assert conversa.motivo_encerramento == "manual_usuario"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_conversas_status_schema.py -v`
Expected: FAIL with TypeError or AttributeError on unknown fields.

- [ ] **Step 3: Update `app.db.models` and create Alembic migration `0018`**

Add fields to `Conversa` class in `backend/src/app/db/models.py`:
```python
    status: Mapped[str] = mapped_column(String(20), default="aberta", index=True)
    encerrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    motivo_encerramento: Mapped[str | None] = mapped_column(String(50), nullable=True)
```

Create migration file `backend/migrations/versions/0018_conversas_status_custos.py`:
```python
"""conversas status e custos

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('conversas', sa.Column('status', sa.String(length=20), server_default='aberta', nullable=False))
    op.add_column('conversas', sa.Column('encerrada_em', sa.DateTime(timezone=True), nullable=True))
    op.add_column('conversas', sa.Column('motivo_encerramento', sa.String(length=50), nullable=True))
    op.create_index('idx_conversas_status', 'conversas', ['status'])
    op.create_index('idx_conversas_encerrada_em', 'conversas', ['encerrada_em'])

def downgrade() -> None:
    op.drop_index('idx_conversas_encerrada_em', table_name='conversas')
    op.drop_index('idx_conversas_status', table_name='conversas')
    op.drop_column('conversas', 'motivo_encerramento')
    op.drop_column('conversas', 'encerrada_em')
    op.drop_column('conversas', 'status')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_conversas_status_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0018_conversas_status_custos.py backend/tests/test_conversas_status_schema.py
git commit -m "feat(db): add status, encerrada_em, and motivo_encerramento to conversas"
```

---

### Task 2: Segregated Cost Accounting in LLM Clients & Chat Data Models

**Files:**
- Modify: `backend/src/app/router/llm_client.py:7-42`
- Modify: `backend/src/app/models/chat.py:128-200`
- Modify: `backend/src/app/router/openrouter_client.py:109-147`
- Test: `backend/tests/test_llm_cost_accounting.py`

**Interfaces:**
- Consumes: `price_per_1k_input_tokens`, `price_per_1k_output_tokens` in `OpenRouterClient`.
- Produces: `cost_prompt_usd`, `cost_completion_usd` in `LLMResponse`, `LLMStreamChunk`, and `ChatDoneEventData`.

- [ ] **Step 1: Write the failing test for cost calculation segregation**

```python
import pytest
from app.router.openrouter_client import OpenRouterClient

def test_openrouter_segregated_cost_calculation():
    client = OpenRouterClient(
        base_url="https://openrouter.ai/api/v1",
        api_key="mock-key",
        model="google/gemini-2.5-flash",
        timeout_s=10.0,
        price_per_1k_input_tokens=0.001,  # $0.001 per 1k input
        price_per_1k_output_tokens=0.003, # $0.003 per 1k output
    )
    cost_prompt, cost_completion, cost_total = client._custo_detalhado(prompt_tokens=1000, completion_tokens=2000)
    assert pytest.approx(cost_prompt, 0.00001) == 0.001
    assert pytest.approx(cost_completion, 0.00001) == 0.006
    assert pytest.approx(cost_total, 0.00001) == 0.007
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_llm_cost_accounting.py -v`
Expected: FAIL with AttributeError "_custo_detalhado".

- [ ] **Step 3: Implement segregated cost methods and schemas**

In `backend/src/app/router/llm_client.py`: Add `cost_prompt_usd: float = 0.0` and `cost_completion_usd: float = 0.0` to `LLMResponse` and `LLMStreamChunk`.

In `backend/src/app/models/chat.py`: Add `cost_prompt_usd: float | None = 0.0` and `cost_completion_usd: float | None = 0.0` to `ChatDoneEventData`.

In `backend/src/app/router/openrouter_client.py`:
```python
    def _custo_detalhado(
        self, prompt_tokens: int | None, completion_tokens: int | None
    ) -> tuple[float, float, float]:
        cost_prompt = (prompt_tokens / 1000.0 * self._price_in) if prompt_tokens else 0.0
        cost_completion = (completion_tokens / 1000.0 * self._price_out) if completion_tokens else 0.0
        return cost_prompt, cost_completion, cost_prompt + cost_completion
```
Update `generate`, `generate_stream`, and `describe_image` to extract tokens from `usage` and populate `cost_prompt_usd` and `cost_completion_usd` (including multimodal vision calls).

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_llm_cost_accounting.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/llm_client.py backend/src/app/models/chat.py backend/src/app/router/openrouter_client.py backend/tests/test_llm_cost_accounting.py
git commit -m "feat(llm): implement prompt and completion cost segregation in OpenRouter client"
```

---

### Task 3: Chat Session Closure API & Inactivity Background Worker

**Files:**
- Create: `backend/src/app/services/chat_closure_service.py`
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/src/app/main.py:lifespan`
- Test: `backend/tests/test_chat_closure.py`

**Interfaces:**
- Consumes: `Conversa` model, `async_session_maker`.
- Produces: `POST /api/chat/conversations/{id}/close` endpoint and background inactivity worker `cerrar_conversas_inativas`.

- [ ] **Step 1: Write failing tests for chat closure API and inactivity worker**

```python
import pytest
from datetime import datetime, timedelta, UTC
from app.db.models import Conversa
from app.services.chat_closure_service import fechar_conversas_inativas

@pytest.mark.asyncio
async def test_inactivity_worker_closes_old_chats(db_session):
    old_chat = Conversa(
        id="old-chat-1",
        status="aberta",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=35)
    )
    recent_chat = Conversa(
        id="recent-chat-2",
        status="aberta",
        atualizada_em=datetime.now(UTC) - timedelta(minutes=10)
    )
    db_session.add_all([old_chat, recent_chat])
    await db_session.commit()

    closed_count = await fechar_conversas_inativas(db_session, timeout_minutes=30)
    assert closed_count == 1

    await db_session.refresh(old_chat)
    await db_session.refresh(recent_chat)
    assert old_chat.status == "encerrada"
    assert old_chat.motivo_encerramento == "inatividade"
    assert recent_chat.status == "aberta"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_chat_closure.py -v`
Expected: FAIL with ImportError "fechar_conversas_inativas not found".

- [ ] **Step 3: Implement chat closure service & endpoints**

Create `backend/src/app/services/chat_closure_service.py`:
```python
from datetime import datetime, timedelta, UTC
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import Conversa

async def fechar_conversas_inativas(session: AsyncSession, timeout_minutes: int = 30) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    stmt = (
        update(Conversa)
        .where(Conversa.status == "aberta")
        .where(Conversa.atualizada_em < cutoff)
        .values(
            status="encerrada",
            encerrada_em=datetime.now(UTC),
            motivo_encerramento="inatividade"
        )
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount
```

Add endpoint in `backend/src/app/api/chat.py`:
```python
@router.post("/conversations/{conversation_id}/close")
async def close_conversation(conversation_id: str, db: AsyncSession = Depends(get_db)):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_chat_closure.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/chat_closure_service.py backend/src/app/api/chat.py backend/src/app/main.py backend/tests/test_chat_closure.py
git commit -m "feat(chat): add conversation closure endpoint and 30-min inactivity worker"
```

---

### Task 4: Analytics REST API (`GET /api/admin/metrics/tokens-and-costs`)

**Files:**
- Create: `backend/src/app/api/admin_metrics.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_admin_metrics_api.py`

**Interfaces:**
- Consumes: `Conversa` and `ConversaMensagem` models.
- Produces: `GET /api/admin/metrics/tokens-and-costs` endpoint.

- [ ] **Step 1: Write failing test for admin metrics API**

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_token_and_cost_metrics(async_client: AsyncClient):
    response = await async_client.get("/api/admin/metrics/tokens-and-costs?period=7d")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "daily_breakdown" in data
    assert "total_closed_chats" in data["summary"]
    assert "total_cost_prompt_usd" in data["summary"]
    assert "total_cost_completion_usd" in data["summary"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_admin_metrics_api.py -v`
Expected: FAIL 404 Not Found.

- [ ] **Step 3: Implement `app/api/admin_metrics.py`**

Build SQL aggregation logic querying `Conversa` join `ConversaMensagem` grouped by `date(Conversa.encerrada_em)` for closed chats, and return `TokenCostMetricsResponse`. Register router in `main.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=backend/src .venv/bin/pytest backend/tests/test_admin_metrics_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/admin_metrics.py backend/src/app/main.py backend/tests/test_admin_metrics_api.py
git commit -m "feat(metrics): add GET /api/admin/metrics/tokens-and-costs analytics endpoint"
```

---

### Task 5: Frontend Metrics Dashboard & Chat Close Button

**Files:**
- Create: `frontend/src/app/admin/metricas/page.tsx`
- Modify: `frontend/src/components/chat/ChatModal.tsx`
- Modify: `frontend/src/components/layout/Header.tsx`
- Test: `frontend/src/tests/AdminMetricasPage.test.tsx`

**Interfaces:**
- Consumes: `GET /api/admin/metrics/tokens-and-costs` and `POST /api/chat/conversations/{id}/close`.
- Produces: Next.js page `/admin/metricas` and chat closure UX button.

- [ ] **Step 1: Write failing test for Frontend Admin Metrics Page**

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect } from 'vitest'
import MetricsPage from '@/app/admin/metricas/page'

vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
  ok: true,
  json: async () => ({
    period: '7d',
    summary: {
      total_closed_chats: 10,
      total_internal_prompt_tokens: 5000,
      total_internal_completion_tokens: 2000,
      total_external_prompt_tokens: 1500,
      total_external_completion_tokens: 600,
      total_cost_prompt_usd: 0.005,
      total_cost_completion_usd: 0.003,
      total_cost_usd: 0.008,
    },
    daily_breakdown: []
  })
}))

describe('Admin Metrics Page', () => {
  it('renders summary cards correctly', async () => {
    render(<MetricsPage />)
    await waitFor(() => {
      expect(screen.getByText('Tokens Internos (GPU Local)')).toBeDefined()
      expect(screen.getByText('$0.0080')).toBeDefined()
    })
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm --prefix frontend test frontend/src/tests/AdminMetricasPage.test.tsx`
Expected: FAIL missing component/page.

- [ ] **Step 3: Implement `/admin/metricas/page.tsx` and Chat closure button**

Create `frontend/src/app/admin/metricas/page.tsx` with KPI cards (Internal tokens, External tokens, Prompt cost, Completion cost, Total cost, Closed chats count) and daily breakdown table.
Update `ChatModal.tsx` to add "Encerrar Atendimento" button calling `/api/chat/conversations/{id}/close`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm --prefix frontend test frontend/src/tests/AdminMetricasPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/app/admin/metricas/page.tsx frontend/src/components/chat/ChatModal.tsx frontend/src/components/layout/Header.tsx frontend/src/tests/AdminMetricasPage.test.tsx
git commit -m "feat(frontend): create /admin/metricas dashboard and add chat closure button"
```
