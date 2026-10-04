# Dashboards e Gráficos Dinâmicos Gerados via Chat com Persistência Permanente Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement dynamic analytical charts generated via Chat by Admin with permanent PostgreSQL persistence (`admin_charts`), inline rich card visualization (`CardGrafico` / `ChatChartCard`), and a permanent dashboard gallery at `/admin/dashboards` with Recharts support.

**Architecture:** A new database table `admin_charts` records chart definitions, aggregations, Recharts configurations, and current data snapshots. A backend aggregation service (`chart_generator.py`) executes pre-compiled analytical SQL queries across catalog, orders, and token metrics. The Chat Orchestrator detects chart requests from authenticated admins, generates & persists the chart, and delivers an inline `CardGrafico` card in the SSE stream. A dedicated REST API (`/api/admin/charts`) handles CRUD and live refresh. The frontend renders dynamic charts using Recharts (`ChartRenderer`), embeds them in chat bubbles (`ChatChartCard`), and organizes them in a grid dashboard (`/admin/dashboards`).

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL, Pydantic v2, TypeScript, React 19, Next.js 16, Recharts, TailwindCSS, Vitest, Pytest.

**Spec:** `docs/superpowers/specs/2026-10-04-dashboards-dinamicos-admin-design.md`

## Global Constraints

- **Python Floor:** Python 3.14 compatible, typing with modern syntax (`X | None`, `list[X]`, `dict[str, Any]`).
- **SQLAlchemy:** 2.0 async style (`Mapped`, `mapped_column`, `select()`, `session.scalar()`).
- **PostgreSQL Persistence:** All generated charts must persist across server restarts in `admin_charts`.
- **Security & Authorization:** Only authenticated Admins (`verificar_admin_por_token`) may generate charts via chat or manage charts via `/api/admin/charts`.
- **Sanitized Aggregations:** Zero raw unsanitized SQL strings from users; pre-compiled query templates only.
- **Frontend Stack:** React 19, Next.js 16 App Router, Recharts for responsive chart rendering, Tailwind CSS.

## Review Focus

1. **Non-admin attempt to generate chart via chat**: Must be gracefully denied with friendly notification without generating or persisting any record in `admin_charts`.
2. **Refresh failure when underlying entity changed or empty data**: Chart refresh endpoint must return 200 with updated empty list `[]` instead of raising 500 error.
3. **Invalid chart query identifier in database**: Service must raise a controlled error or fallback instead of executing arbitrary SQL.
4. **Missing or malformed config_json in Recharts renderer**: Frontend `ChartRenderer` must safely handle empty `dados` or missing `x_key`/`y_keys` without crashing or throwing React runtime errors.
5. **Reordering and pin toggling synchronization**: Dashboard UI must immediately reflect local pin/unpin/delete actions and synchronize with REST API.

---

### Task 1: Migration 0019 & AdminChart Model

**Files:**
- Create: `backend/migrations/versions/0019_admin_charts.py`
- Modify: `backend/src/app/db/models.py`
- Test: `backend/tests/test_admin_charts_model.py`

**Interfaces:**
- Consumes: `Base`, `_JsonVariant` from `app.db.models`
- Produces: `AdminChart` model with fields (`id`, `titulo`, `descricao`, `tipo_grafico`, `config_json`, `dados_json`, `sql_query`, `fixado`, `ordem`, `criado_por`, `criado_em`, `atualizado_em`)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_charts_model.py
import uuid
import pytest
from sqlalchemy import select
from app.db.models import AdminChart

@pytest.mark.asyncio
async def test_admin_chart_model_crud(db_session):
    chart = AdminChart(
        titulo="Vendas por Categoria",
        descricao="Gráfico de teste",
        tipo_grafico="bar",
        config_json={"x_key": "categoria", "y_keys": ["total_vendas_brl"]},
        dados_json=[{"categoria": "Elétrica", "total_vendas_brl": 1500.0}],
        sql_query="vendas_por_categoria",
        fixado=True,
        ordem=1,
        criado_por="admin@empresa.com",
    )
    db_session.add(chart)
    await db_session.commit()
    await db_session.refresh(chart)

    assert isinstance(chart.id, uuid.UUID)
    assert chart.titulo == "Vendas por Categoria"
    assert chart.fixado is True
    assert chart.dados_json[0]["categoria"] == "Elétrica"

    # Query back
    result = await db_session.scalar(select(AdminChart).where(AdminChart.id == chart.id))
    assert result is not None
    assert result.tipo_grafico == "bar"

    # Delete
    await db_session.delete(result)
    await db_session.commit()
    check = await db_session.scalar(select(AdminChart).where(AdminChart.id == chart.id))
    assert check is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_charts_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'AdminChart' from 'app.db.models'`

- [ ] **Step 3: Write minimal implementation**

1. Create `backend/migrations/versions/0019_admin_charts.py`:
```python
"""admin charts table

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-04

"""
from collections.abc import Sequence
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_JsonVariant = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "admin_charts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("titulo", sa.String(length=255), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("tipo_grafico", sa.String(length=50), nullable=False),
        sa.Column("config_json", _JsonVariant, nullable=False),
        sa.Column("dados_json", _JsonVariant, nullable=False),
        sa.Column("sql_query", sa.Text(), nullable=True),
        sa.Column("fixado", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.Column("criado_por", sa.String(length=255), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_admin_charts_fixado", "admin_charts", ["fixado"])
    op.create_index("idx_admin_charts_criado_em", "admin_charts", ["criado_em"])
    op.create_index("idx_admin_charts_ordem", "admin_charts", ["ordem"])


def downgrade() -> None:
    op.drop_index("idx_admin_charts_ordem", table_name="admin_charts")
    op.drop_index("idx_admin_charts_criado_em", table_name="admin_charts")
    op.drop_index("idx_admin_charts_fixado", table_name="admin_charts")
    op.drop_table("admin_charts")
```

2. Add `AdminChart` to `backend/src/app/db/models.py`:
```python
class AdminChart(Base):
    """Gráficos dinâmicos gerados via chat pelo Administrador e persistidos
    para exibição no painel permanente /admin/dashboards.
    """

    __tablename__ = "admin_charts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    tipo_grafico: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(_JsonVariant, nullable=False, default=dict)
    dados_json: Mapped[list] = mapped_column(_JsonVariant, nullable=False, default=list)
    sql_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    fixado: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    ordem: Mapped[int] = mapped_column(default=0, index=True)
    criado_por: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

3. Run `alembic upgrade head`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_charts_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0019_admin_charts.py backend/src/app/db/models.py backend/tests/test_admin_charts_model.py
git commit -m "feat(db): add 0019 migration and AdminChart model for dynamic dashboards"
```

---

### Task 2: Chart Aggregations Service (`chart_generator.py`)

**Files:**
- Create: `backend/src/app/services/chart_generator.py`
- Test: `backend/tests/test_chart_generator.py`

**Interfaces:**
- Consumes: `AsyncSession`, `Produto`, `Pedido`, `PedidoItem`, `ProdutoEstoque`, `ConversaMensagem`
- Produces:
  - `SUPPORTED_QUERIES`: dict of registered aggregation keys
  - `execute_chart_aggregation(session: AsyncSession, query_key: str) -> tuple[dict, list[dict]]`
  - `detect_chart_request(prompt: str) -> dict | None`
  - `generate_and_persist_chart(session: AsyncSession, prompt: str, user_email: str) -> AdminChart | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chart_generator.py
import pytest
from app.services.chart_generator import (
    detect_chart_request,
    execute_chart_aggregation,
    generate_and_persist_chart,
)
from app.db.models import Produto, ProdutoEstoque, AdminChart

@pytest.mark.asyncio
async def test_detect_chart_request():
    assert detect_chart_request("gere um gráfico de vendas por categoria") is not None
    assert detect_chart_request("mostre o estoque num gráfico de pizza") is not None
    assert detect_chart_request("como trocar meu produto?") is None

@pytest.mark.asyncio
async def test_execute_chart_aggregation_vendas(db_session):
    p = Produto(nome="Chave Teste", descricao="Desc", preco=50.0, categoria="Ferramentas")
    db_session.add(p)
    await db_session.commit()

    config, data = await execute_chart_aggregation(db_session, "vendas_por_categoria")
    assert "x_key" in config
    assert isinstance(data, list)

@pytest.mark.asyncio
async def test_generate_and_persist_chart(db_session):
    chart = await generate_and_persist_chart(
        db_session,
        prompt="crie um gráfico de barras com os estoques por centro de distribuição",
        user_email="admin@empresa.com",
    )
    assert chart is not None
    assert isinstance(chart, AdminChart)
    assert chart.tipo_grafico in ["bar", "pie", "donut", "line", "area"]
    assert chart.criado_por == "admin@empresa.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/test_chart_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.chart_generator'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/app/services/chart_generator.py`:
- Implement `detect_chart_request(prompt: str) -> dict | None`:
  - Analyzes prompt for chart intent keywords (`gráfico`, `grafico`, `dashboard`) + chart type (`barra`, `linha`, `pizza`, `área`, `donut`) + metric target (`vendas`, `categoria`, `estoque`, `cd`, `centro de distribuição`, `pedidos`, `status`, `tokens`, `custos`).
- Implement aggregations:
  1. `vendas_por_categoria`: calculates total products and estimated sales value per category.
  2. `estoque_por_cd`: sums `quantidade` grouped by `centro_distribuicao`.
  3. `pedidos_por_status`: counts orders grouped by `status`.
  4. `metricas_tokens_por_dia`: aggregates message tokens / costs grouped by message creation date.
- Implement `execute_chart_aggregation(session: AsyncSession, query_key: str) -> tuple[dict, list[dict]]`: executes pre-compiled aggregation and returns `(config_json, dados_json)`.
- Implement `generate_and_persist_chart(session: AsyncSession, prompt: str, user_email: str) -> AdminChart | None`: detects intent, runs aggregation, creates `AdminChart` entity, adds to session and commits, returning the instance.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/pytest backend/tests/test_chart_generator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/services/chart_generator.py backend/tests/test_chart_generator.py
git commit -m "feat(charts): add chart_generator service with analytical aggregations"
```

---

### Task 3: REST API Endpoints (`/api/admin/charts`)

**Files:**
- Create: `backend/src/app/api/admin_charts.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_admin_charts_api.py`

**Interfaces:**
- Consumes: `AdminChart`, `get_db_session`, `verificar_admin_por_token`, `execute_chart_aggregation`
- Produces:
  - `GET /api/admin/charts`
  - `POST /api/admin/charts`
  - `POST /api/admin/charts/{id}/refresh`
  - `PUT /api/admin/charts/{id}`
  - `DELETE /api/admin/charts/{id}`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_admin_charts_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.models import AdminChart, Cliente

@pytest.mark.asyncio
async def test_admin_charts_api_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/charts")
        assert res.status_code == 403

@pytest.mark.asyncio
async def test_admin_charts_crud_flow(db_session):
    # Setup admin user
    admin = Cliente(nome="Admin Master", email="admin@empresa.com")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)

    admin_token = f"mock-token-{admin.id}"
    headers = {"Authorization": f"Bearer {admin_token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create chart
        payload = {
            "titulo": "Gráfico de Teste",
            "descricao": "Descrição",
            "tipo_grafico": "bar",
            "config_json": {"x_key": "cat", "y_keys": ["val"]},
            "dados_json": [{"cat": "A", "val": 10}],
            "sql_query": "vendas_por_categoria",
            "fixado": True,
            "ordem": 0,
        }
        res_create = await client.post("/api/admin/charts", json=payload, headers=headers)
        assert res_create.status_code == 201
        chart_id = res_create.json()["id"]

        # List charts
        res_list = await client.get("/api/admin/charts", headers=headers)
        assert res_list.status_code == 200
        items = res_list.json()
        assert len(items) >= 1

        # Refresh chart
        res_refresh = await client.post(f"/api/admin/charts/{chart_id}/refresh", headers=headers)
        assert res_refresh.status_code == 200

        # Update chart
        res_update = await client.put(f"/api/admin/charts/{chart_id}", json={"titulo": "Novo Titulo", "fixado": False}, headers=headers)
        assert res_update.status_code == 200
        assert res_update.json()["titulo"] == "Novo Titulo"
        assert res_update.json()["fixado"] is False

        # Delete chart
        res_del = await client.delete(f"/api/admin/charts/{chart_id}", headers=headers)
        assert res_del.status_code == 200

        # Verify deleted
        res_list_after = await client.get("/api/admin/charts", headers=headers)
        assert not any(c["id"] == chart_id for c in res_list_after.json())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_charts_api.py -v`
Expected: FAIL (404 Not Found since endpoint is not registered)

- [ ] **Step 3: Write minimal implementation**

1. Create `backend/src/app/api/admin_charts.py`:
- Extract auth token from `Authorization` header (`Bearer ...`) or `X-Auth-Token` header.
- Verify admin permissions using `verificar_admin_por_token(session, token)`.
- Implement `GET /api/admin/charts`: return list sorted by `fixado.desc(), ordem.asc(), criado_em.desc()`.
- Implement `POST /api/admin/charts`: validate payload with Pydantic model `AdminChartCreate`, persist `AdminChart`, return status 201.
- Implement `POST /api/admin/charts/{id}/refresh`: look up chart, if `sql_query` is defined in `SUPPORTED_QUERIES`, call `execute_chart_aggregation` and update `dados_json`, `config_json`, and `atualizado_em`. Return updated chart.
- Implement `PUT /api/admin/charts/{id}`: allow updating `titulo`, `descricao`, `fixado`, `ordem`, `tipo_grafico`.
- Implement `DELETE /api/admin/charts/{id}`: delete chart by ID, return `{"ok": True}`.

2. Register `admin_charts_router` in `backend/src/app/main.py`:
```python
from app.api.admin_charts import router as admin_charts_router
...
app.include_router(admin_charts_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/pytest backend/tests/test_admin_charts_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/api/admin_charts.py backend/src/app/main.py backend/tests/test_admin_charts_api.py
git commit -m "feat(api): add admin charts CRUD and refresh REST endpoints"
```

---

### Task 4: Chat Orchestrator & CardGrafico Integration

**Files:**
- Modify: `backend/src/app/models/chat.py`
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/src/app/api/chat.py`
- Test: `backend/tests/test_chat_chart_card.py`

**Interfaces:**
- Consumes: `CardGrafico` model, `generate_and_persist_chart` from `chart_generator.py`
- Produces: `ChatCard` union with `CardGrafico`, `CardGrafico` in SSE `done` event.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_chat_chart_card.py
import pytest
from app.models.chat import CardGrafico, ChatCard, ChatDoneEventData
from pydantic import TypeAdapter

def test_card_grafico_schema():
    card = CardGrafico(
        chart_id="123e4567-e89b-12d3-a456-426614174000",
        titulo="Vendas por Categoria",
        tipo_grafico="bar",
        config={"x_key": "categoria", "y_keys": ["total"]},
        dados=[{"categoria": "Ferramentas", "total": 100}],
        fixado=True,
    )
    assert card.tipo == "grafico"
    assert card.tipo_grafico == "bar"

    adapter = TypeAdapter(ChatCard)
    dumped = adapter.dump_python(card)
    assert dumped["tipo"] == "grafico"

    done = ChatDoneEventData(
        domain="vendas",
        backend_used="local",
        card=card,
    )
    assert done.card.tipo == "grafico"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_chart_card.py -v`
Expected: FAIL with `ImportError: cannot import name 'CardGrafico' from 'app.models.chat'`

- [ ] **Step 3: Write minimal implementation**

1. In `backend/src/app/models/chat.py`:
- Define `CardGrafico`:
```python
class CardGrafico(BaseModel):
    """Card rico de gráfico analítico dinâmico gerado via chat."""
    tipo: Literal["grafico"] = "grafico"
    chart_id: str
    titulo: str
    tipo_grafico: Literal["bar", "line", "pie", "area", "donut"]
    config: dict = Field(default_factory=dict)
    dados: list[dict] = Field(default_factory=list)
    fixado: bool = True
```
- Update `ChatCard`:
```python
ChatCard = Annotated[CardProduto | CardCotacao | CardAgendamento | CardGrafico, Field(discriminator="tipo")]
```

2. In `backend/src/app/router/orchestrator.py`:
- Add parameter `is_admin: bool = False`, `user_email: str | None = None` to `handle_message`.
- Detect chart generation request via `detect_chart_request(message)`.
- If request is a chart request:
  - If `is_admin` is True and `db_sessionmaker` is present:
    - Open session, execute `generate_and_persist_chart(session, message, user_email or "admin")`.
    - Build `CardGrafico` from returned `AdminChart`.
    - Yield `TokenEvent(text=f"Gerei o gráfico '{chart.titulo}' para você com base nos dados mais recentes. Ele já está salvo no seu painel de Dashboards.")`.
    - Yield `RouterDecision(domain="atendimento", backend_escolhido="local", card=card_grafico, ...)`.
    - Return early.
  - If `is_admin` is False:
    - Yield `TokenEvent(text="A geração de gráficos e dashboards personalizados é um recurso exclusivo para administradores autenticados. Faça login como administrador para gerar e visualizar gráficos dinâmicos.")`.
    - Yield `RouterDecision(domain="fora_escopo", backend_escolhido="local", ...)`.
    - Return early.

3. In `backend/src/app/api/chat.py`:
- Pass `is_admin=is_admin, user_email=email_cliente` into `handle_message(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/pytest backend/tests/test_chat_chart_card.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/models/chat.py backend/src/app/router/orchestrator.py backend/src/app/api/chat.py backend/tests/test_chat_chart_card.py
git commit -m "feat(chat): add CardGrafico model and orchestrator dynamic chart generation"
```

---

### Task 5: Frontend Recharts ChartRenderer Component

**Files:**
- Create: `frontend/components/charts/ChartRenderer.tsx`
- Modify: `frontend/lib/types/chat.ts`
- Test: `frontend/tests/components/ChartRenderer.test.tsx`

**Interfaces:**
- Consumes: Recharts library (`ResponsiveContainer`, `BarChart`, `LineChart`, `PieChart`, `AreaChart`, etc.)
- Produces: `ChartRenderer({ tipo_grafico, config, dados, height?: number })`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/components/ChartRenderer.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChartRenderer from "@/components/charts/ChartRenderer";

// Mock ResponsiveContainer for jsdom
vi.mock("recharts", async () => {
  const original = await vi.importActual("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  };
});

describe("ChartRenderer", () => {
  it("renders empty state gracefully when data is empty", () => {
    render(<ChartRenderer tipo_grafico="bar" config={{}} dados={[]} />);
    expect(screen.getByText(/Nenhum dado disponível/i)).toBeInTheDocument();
  });

  it("renders bar chart container with data", () => {
    const dados = [
      { categoria: "Cat A", total: 100 },
      { categoria: "Cat B", total: 200 },
    ];
    const config = { x_key: "categoria", y_keys: ["total"], labels: { total: "Total (R$)" } };
    const { container } = render(<ChartRenderer tipo_grafico="bar" config={config} dados={dados} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test tests/components/ChartRenderer.test.tsx`
Expected: FAIL with `Cannot find module '@/components/charts/ChartRenderer'`

- [ ] **Step 3: Write minimal implementation**

1. In `frontend/lib/types/chat.ts`:
- Add `ChatCardGrafico` interface:
```typescript
export interface ChatCardGrafico {
  tipo: "grafico";
  chart_id: string;
  titulo: string;
  tipo_grafico: "bar" | "line" | "pie" | "area" | "donut";
  config: {
    x_key?: string;
    y_keys?: string[];
    labels?: Record<string, string>;
    format?: "currency" | "number" | "percent";
    palette?: string[];
    [key: string]: unknown;
  };
  dados: Array<Record<string, unknown>>;
  fixado?: boolean;
}
```
- Update `ChatCard`:
```typescript
export type ChatCard = ChatCardProduto | ChatCardCotacao | ChatCardAgendamento | ChatCardGrafico;
```

2. Create `frontend/components/charts/ChartRenderer.tsx`:
- Accepts `tipo_grafico`, `config`, `dados`, `height = 280`.
- Supports "bar", "line", "pie", "area", "donut".
- Formats values using currency/number helper.
- Uses color palette: `palette || ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]`.
- Handles empty state (`dados.length === 0`) cleanly.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test tests/components/ChartRenderer.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/types/chat.ts frontend/components/charts/ChartRenderer.tsx frontend/tests/components/ChartRenderer.test.tsx
git commit -m "feat(frontend): create ChartRenderer component with Recharts"
```

---

### Task 6: Frontend DynamicChartCard & ChatChartCard Integration

**Files:**
- Create: `frontend/components/chat/cards/ChatChartCard.tsx`
- Create: `frontend/components/admin/DynamicChartCard.tsx`
- Modify: `frontend/components/chat/cards/ChatCard.tsx`
- Modify: `frontend/components/chat/MessageBubble.tsx`
- Test: `frontend/tests/components/ChatChartCard.test.tsx`

**Interfaces:**
- Consumes: `ChatCardGrafico`, `ChartRenderer`
- Produces: `ChatChartCard`, `DynamicChartCard`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/components/ChatChartCard.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import ChatChartCard from "@/components/chat/cards/ChatChartCard";
import type { ChatCardGrafico } from "@/lib/types/chat";

vi.mock("recharts", async () => {
  const original = await vi.importActual("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
  };
});

describe("ChatChartCard", () => {
  const mockCard: ChatCardGrafico = {
    tipo: "grafico",
    chart_id: "test-uuid-1",
    titulo: "Vendas por Categoria",
    tipo_grafico: "bar",
    config: { x_key: "cat", y_keys: ["val"] },
    dados: [{ cat: "A", val: 50 }],
    fixado: true,
  };

  it("renders chart title and dashboard link", () => {
    render(<ChatChartCard card={mockCard} />);
    expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
    expect(screen.getByText(/Ver no painel de dashboards/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test tests/components/ChatChartCard.test.tsx`
Expected: FAIL with `Cannot find module '@/components/chat/cards/ChatChartCard'`

- [ ] **Step 3: Write minimal implementation**

1. Create `frontend/components/chat/cards/ChatChartCard.tsx`:
- Renders header with chart title, badge with chart type, embedded `ChartRenderer`, and bottom link button `<Link href="/admin/dashboards">Ver no painel de dashboards →</Link>`.

2. Update `frontend/components/chat/cards/ChatCard.tsx`:
- Add `case "grafico": return <ChatChartCard card={card} />;`.

3. Create `frontend/components/admin/DynamicChartCard.tsx`:
- Card container for `/admin/dashboards`.
- Header: Title, description, editable title mode, Refresh button (🔄), Pin toggle (📌), Delete button (🗑️).
- Body: `ChartRenderer`.
- Footer: "Atualizado em [data/hora]" and query tag.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test tests/components/ChatChartCard.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/components/chat/cards/ChatChartCard.tsx frontend/components/admin/DynamicChartCard.tsx frontend/components/chat/cards/ChatCard.tsx frontend/tests/components/ChatChartCard.test.tsx
git commit -m "feat(frontend): add ChatChartCard and DynamicChartCard components"
```

---

### Task 7: Frontend `/admin/dashboards` Page & AdminGearMenu Link

**Files:**
- Create: `frontend/lib/api/charts.ts`
- Create: `frontend/app/admin/dashboards/page.tsx`
- Modify: `frontend/components/layout/AdminGearMenu.tsx`
- Test: `frontend/tests/components/AdminDashboardsPage.test.tsx`

**Interfaces:**
- Consumes: `/api/admin/charts` REST API, `useAuthStore`
- Produces: Complete Admin Dashboards UI at `/admin/dashboards` and menu entry in `AdminGearMenu`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/tests/components/AdminDashboardsPage.test.tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import AdminDashboardsPage from "@/app/admin/dashboards/page";

vi.mock("@/lib/hooks/useAuthStore", () => ({
  useAuthStore: () => ({
    user: { id: 1, nome: "Admin", email: "admin@empresa.com", perfil: "Admin" },
    token: "mock-token-1",
  }),
}));

vi.mock("@/lib/api/charts", () => ({
  fetchAdminCharts: vi.fn().mockResolvedValue([
    {
      id: "chart-1",
      titulo: "Receita por Mês",
      descricao: "Histórico recente",
      tipo_grafico: "bar",
      config_json: { x_key: "mes", y_keys: ["receita"] },
      dados_json: [{ mes: "Jan", receita: 1000 }],
      fixado: true,
      ordem: 0,
      criado_em: "2026-10-04T00:00:00Z",
      atualizado_em: "2026-10-04T00:00:00Z",
    },
  ]),
  refreshAdminChart: vi.fn(),
  updateAdminChart: vi.fn(),
  deleteAdminChart: vi.fn(),
}));

describe("AdminDashboardsPage", () => {
  it("renders page title and charts list", async () => {
    render(<AdminDashboardsPage />);
    expect(screen.getByText(/Dashboards & Gráficos/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Receita por Mês")).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test tests/components/AdminDashboardsPage.test.tsx`
Expected: FAIL with `Cannot find module '@/lib/api/charts'`

- [ ] **Step 3: Write minimal implementation**

1. Create `frontend/lib/api/charts.ts`:
- Define `AdminChartItem` interface.
- Implement `fetchAdminCharts(token: string)`
- Implement `refreshAdminChart(id: string, token: string)`
- Implement `updateAdminChart(id: string, payload: Partial<AdminChartItem>, token: string)`
- Implement `deleteAdminChart(id: string, token: string)`

2. Create `frontend/app/admin/dashboards/page.tsx`:
- Header: Breadcrumb "Início > Administração > Dashboards", Title "Dashboards & Gráficos", Refresh All button, filter tabs (Todos, Apenas Fixados).
- Grid: Responsive grid displaying `DynamicChartCard` items.
- Empty state: "Nenhum gráfico gerado ainda. Peça ao assistente no chat: 'Gere um gráfico de vendas por categoria'".
- Permission check: Redirects or displays alert if user is not Admin.

3. Update `frontend/components/layout/AdminGearMenu.tsx`:
- Add menu item "📈 Dashboards & Gráficos" linking to `/admin/dashboards`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test tests/components/AdminDashboardsPage.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api/charts.ts frontend/app/admin/dashboards/page.tsx frontend/components/layout/AdminGearMenu.tsx frontend/tests/components/AdminDashboardsPage.test.tsx
git commit -m "feat(dashboards): add admin dashboards page and gear menu integration"
```

---

### Task 8: Verification, Documentation & Roadmap Update

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ADMIN_MANUAL.md` (or relevant doc)
- Run: Pytest full suite, Vitest full suite, Next.js build.

- [ ] **Step 1: Run all backend tests**
Run: `backend/.venv/bin/pytest backend/tests -v`
Expected: PASS (805+ tests)

- [ ] **Step 2: Run all frontend tests**
Run: `cd frontend && npm test`
Expected: PASS (356+ tests)

- [ ] **Step 3: Run frontend build check**
Run: `cd frontend && npm run build`
Expected: PASS (Clean build with zero errors)

- [ ] **Step 4: Update Documentation & Roadmap**
- Mark roadmap item as completed in `docs/ROADMAP.md`.
- Document chart generation and `/admin/dashboards` in `docs/ADMIN_MANUAL.md` or `docs/MANUAL_USUARIO.md`.

- [ ] **Step 5: Commit**
```bash
git add docs/ROADMAP.md docs/
git commit -m "docs(roadmap): mark dynamic charts and dashboards roadmap item as complete"
```
