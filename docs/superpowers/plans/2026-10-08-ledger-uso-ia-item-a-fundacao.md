# Ledger Unificado de Uso de IA — Item A (Fundação) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar a tabela `ai_usage_events` e a função central `registrar_uso_ia` — a fundação de um ledger unificado de uso de IA (origem × ambiente × modelo), sem conectar nenhum ponto de chamada real ainda.

**Architecture:** Novo modelo SQLAlchemy + migração Alembic (schema), novo módulo de serviço `app.services.ai_usage` que espelha o padrão de sessão já aceito em `app.services.ingestion_metrics.record_ingestion_cost` (sessão explícita / sessão própria via factory / fallback para um sessionmaker global configurado uma vez em `app.main`), e a mesma linha de bootstrap em `app.main` que já existe para `ingestion_metrics`.

**Tech Stack:** Python 3.14, SQLAlchemy 2.0 (async), Alembic, pytest + pytest-asyncio, SQLite em memória para os testes (mesmo padrão de `tests/test_memory_store.py`).

**Spec:** `docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md`

## Global Constraints

- Nenhuma dependência nova.
- `registrar_uso_ia` nunca lança exceção — qualquer falha (banco indisponível, sessionmaker não configurado) vira `logger.warning` e retorno `None`. Telemetria é conveniência, nunca pode derrubar a chamada de IA real que ela está registrando.
- Valores numéricos default são `0`/`0.0`, nunca `NULL` — "não se aplica" (ex.: CLIP sem tokens) e "não informado" são o mesmo valor (`0`), mesma convenção já usada em `IngestionCostEvent`.
- Este plano **não conecta nenhum ponto de chamada real** (chat, B2B, admin) a `registrar_uso_ia` — isso é escopo dos itens B/C/D, já registrados como itens próprios em `docs/ROADMAP.md` ("Extra fora do MVP — Ledger Unificado de Uso de IA"), cada um com sua própria spec/plano.
- Nenhuma mudança em `app.services.ingestion_metrics`/`IngestionCostEvent` — ficam exatamente como estão; decidir o futuro deles é explicitamente fora de escopo desta spec (ver spec §6).

---

### Task 1: Modelo `AiUsageEvent` + Migração Alembic

**Files:**
- Modify: `backend/src/app/db/models.py` (adicionar ao final do arquivo, depois de `IngestionCostEvent`)
- Create: `backend/migrations/versions/0024_ai_usage_events.py`
- Test: `backend/tests/test_ai_usage.py` (criado aqui, só o primeiro teste — os demais entram na Task 2)

**Interfaces:**
- Produces: `app.db.models.AiUsageEvent` — colunas `id: uuid.UUID`, `origem: str`, `ambiente: str`, `modelo: str`, `operacao: str`, `tokens_entrada: int` (default 0), `tokens_saida: int` (default 0), `custo_usd: float` (default 0.0), `referencia_id: str | None`, `criado_em: datetime`.

- [ ] **Step 1: Escrever o teste do modelo (falha: `AiUsageEvent` não existe)**

Criar `backend/tests/test_ai_usage.py`:

```python
"""Ledger unificado de uso de IA (origem × ambiente × modelo) —
`app.services.ai_usage` / `app.db.models.AiUsageEvent`. Ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md.
"""

from sqlalchemy import select

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import AiUsageEvent, Base


async def _engine_e_sessionmaker_vazios():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, create_session_factory(engine)


async def test_ai_usage_event_grava_e_le_com_defaults_corretos():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        async with factory() as session:
            evento = AiUsageEvent(
                origem="chat",
                ambiente="interno",
                modelo="clip",
                operacao="identificacao_imagem_clip",
            )
            session.add(evento)
            await session.commit()

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            eventos = resultado.scalars().all()

        assert len(eventos) == 1
        salvo = eventos[0]
        assert salvo.origem == "chat"
        assert salvo.ambiente == "interno"
        assert salvo.modelo == "clip"
        assert salvo.operacao == "identificacao_imagem_clip"
        # Defaults: "não se aplica" é 0/0.0, nunca None.
        assert salvo.tokens_entrada == 0
        assert salvo.tokens_saida == 0
        assert salvo.custo_usd == 0.0
        assert salvo.referencia_id is None
        assert salvo.criado_em is not None
    finally:
        await engine.dispose()
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `cd backend && .venv/bin/pytest tests/test_ai_usage.py -v`
Expected: FAIL com `ImportError: cannot import name 'AiUsageEvent' from 'app.db.models'`

- [ ] **Step 3: Implementar o modelo em `backend/src/app/db/models.py`**

Todos os imports necessários (`uuid`, `datetime`, `DateTime`, `String`,
`func`, `Mapped`, `mapped_column`) já existem no topo do arquivo — não
precisa adicionar nenhum import novo. Adicionar ao final do arquivo
(depois da classe `IngestionCostEvent`):

```python
class AiUsageEvent(Base):
    """Ledger unificado de uso de IA — todo ponto do sistema que chama um
    modelo/engine (local ou externo, texto ou visão) registra um evento
    aqui, via `app.services.ai_usage.registrar_uso_ia`. Substitui a
    necessidade de inferir origem/ambiente a partir de campos espalhados
    em `ConversaMensagem.metricas`/`IngestionCostEvent` (que continuam
    existindo, sem mudança — ver decisão em
    docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md §6).
    """

    __tablename__ = "ai_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    origem: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    ambiente: Mapped[str] = mapped_column(String(20), nullable=False)
    modelo: Mapped[str] = mapped_column(String(100), nullable=False)
    operacao: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tokens_entrada: Mapped[int] = mapped_column(default=0)
    tokens_saida: Mapped[int] = mapped_column(default=0)
    custo_usd: Mapped[float] = mapped_column(default=0.0)
    referencia_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
```

- [ ] **Step 4: Rodar o teste para confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_ai_usage.py -v`
Expected: PASS (1 teste)

- [ ] **Step 5: Criar a migração Alembic**

Criar `backend/migrations/versions/0024_ai_usage_events.py` (mesmo formato
exato de `migrations/versions/0020_ingestion_cost_events.py`):

```python
"""ai usage events table

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-08

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("origem", sa.String(length=50), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False),
        sa.Column("modelo", sa.String(length=100), nullable=False),
        sa.Column("operacao", sa.String(length=100), nullable=False),
        sa.Column("tokens_entrada", sa.Integer(), server_default="0", nullable=False),
        sa.Column("tokens_saida", sa.Integer(), server_default="0", nullable=False),
        sa.Column("custo_usd", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("referencia_id", sa.String(length=500), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_ai_usage_events_origem", "ai_usage_events", ["origem"])
    op.create_index("idx_ai_usage_events_operacao", "ai_usage_events", ["operacao"])
    op.create_index("idx_ai_usage_events_criado_em", "ai_usage_events", ["criado_em"])


def downgrade() -> None:
    op.drop_index("idx_ai_usage_events_criado_em", table_name="ai_usage_events")
    op.drop_index("idx_ai_usage_events_operacao", table_name="ai_usage_events")
    op.drop_index("idx_ai_usage_events_origem", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
```

**Verificar que `0023` é de fato a revisão mais recente antes de escrever
este arquivo:** `ls backend/migrations/versions/ | sort | tail -3`. Se já
existir uma `0024` (outra sessão/ferramenta pode ter avançado o repo
nesse intervalo — ver `docs/AGENTIC_WORKFLOW.md`), renumerar esta
migração e seu `down_revision` de acordo, mantendo a cadeia linear.

- [ ] **Step 6: Commit**

```bash
cd backend
git add src/app/db/models.py migrations/versions/0024_ai_usage_events.py tests/test_ai_usage.py
git commit -m "feat(telemetria): adiciona modelo e migração AiUsageEvent (item A do ledger de uso de IA)"
```

---

### Task 2: Função `registrar_uso_ia` + `set_global_sessionmaker`

**Files:**
- Create: `backend/src/app/services/ai_usage.py`
- Test: `backend/tests/test_ai_usage.py` (acrescentar ao arquivo da Task 1)

**Interfaces:**
- Consumes: `app.db.models.AiUsageEvent` (Task 1).
- Produces: `app.services.ai_usage.registrar_uso_ia(*, origem: str, ambiente: str, modelo: str, operacao: str, tokens_entrada: int = 0, tokens_saida: int = 0, custo_usd: float = 0.0, referencia_id: str | None = None, session: AsyncSession | None = None, session_factory: async_sessionmaker[AsyncSession] | None = None, commit: bool = False) -> AiUsageEvent | None` e `app.services.ai_usage.set_global_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession] | None) -> None` — usados por B/C/D (fora deste plano) e por `app.main` (Task 3).

- [ ] **Step 1: Escrever os 5 testes novos (falham: módulo não existe)**

Acrescentar ao final de `backend/tests/test_ai_usage.py`:

```python
import logging

import pytest

from app.services.ai_usage import registrar_uso_ia, set_global_sessionmaker


async def test_registrar_uso_ia_com_session_explicita_grava():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        async with factory() as session:
            evento = await registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo="gpt-4o-mini",
                operacao="geracao_texto",
                tokens_entrada=120,
                tokens_saida=40,
                custo_usd=0.0021,
                referencia_id="conv-123",
                session=session,
            )
            assert evento is not None

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].referencia_id == "conv-123"
        assert salvos[0].custo_usd == 0.0021
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_com_session_factory_fire_and_forget_grava():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        evento = await registrar_uso_ia(
            origem="admin",
            ambiente="externo",
            modelo="gemini-2.5-flash",
            operacao="extracao_catalogo_visao",
            session_factory=factory,
        )
        assert evento is not None

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].origem == "admin"
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_sem_session_nem_factory_usa_fallback_global():
    engine, factory = await _engine_e_sessionmaker_vazios()
    try:
        set_global_sessionmaker(factory)
        try:
            evento = await registrar_uso_ia(
                origem="chat",
                ambiente="externo",
                modelo="jev",
                operacao="classificacao_jev",
            )
            assert evento is not None
        finally:
            set_global_sessionmaker(None)

        async with factory() as session:
            resultado = await session.execute(select(AiUsageEvent))
            salvos = resultado.scalars().all()
        assert len(salvos) == 1
        assert salvos[0].modelo == "jev"
    finally:
        await engine.dispose()


async def test_registrar_uso_ia_sem_nenhuma_sessao_disponivel_devolve_none_sem_lancar():
    set_global_sessionmaker(None)
    evento = await registrar_uso_ia(
        origem="chat",
        ambiente="interno",
        modelo="clip",
        operacao="identificacao_imagem_clip",
    )
    assert evento is None


async def test_registrar_uso_ia_com_factory_que_falha_devolve_none_e_loga(caplog):
    class _SessionFactoryQuebrada:
        def __call__(self):
            return self

        async def __aenter__(self):
            raise ConnectionError("sem banco nos testes")

        async def __aexit__(self, *exc_info):
            return False

    with caplog.at_level(logging.WARNING, logger="assistente.ai_usage"):
        evento = await registrar_uso_ia(
            origem="b2b",
            ambiente="externo",
            modelo="gpt-4o-mini",
            operacao="comprovante_visao",
            session_factory=_SessionFactoryQuebrada(),
        )

    assert evento is None
    assert any("Falha ao registrar AiUsageEvent" in r.message for r in caplog.records)
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `cd backend && .venv/bin/pytest tests/test_ai_usage.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.ai_usage'` (os 5 testes novos; o teste da Task 1 continua passando)

- [ ] **Step 3: Implementar `backend/src/app/services/ai_usage.py`**

```python
"""Ledger unificado de uso de IA (origem × ambiente × modelo) — ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md.

Todo ponto do sistema que usa um modelo/engine de IA (local ou externo,
texto ou visão) chama `registrar_uso_ia`. Mesmo padrão de sessão de
`app.services.ingestion_metrics.record_ingestion_cost` (sessão explícita /
sessão própria via factory / fallback para um sessionmaker global
configurado uma vez em `app.main`) — reaproveitado de propósito em vez de
inventar uma convenção nova; os dois serviços continuam independentes
(decisão sobre unificá-los fica para quando a origem "admin" for
conectada, ver spec §6).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AiUsageEvent

logger = logging.getLogger("assistente.ai_usage")

_global_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def set_global_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession] | None) -> None:
    """Configura o sessionmaker global usado quando nenhuma sessão/factory
    explícita é passada — chamado uma vez em `app.main` (lifespan)."""
    global _global_sessionmaker
    _global_sessionmaker = sessionmaker


async def registrar_uso_ia(
    *,
    origem: str,
    ambiente: str,
    modelo: str,
    operacao: str,
    tokens_entrada: int = 0,
    tokens_saida: int = 0,
    custo_usd: float = 0.0,
    referencia_id: str | None = None,
    session: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    commit: bool = False,
) -> AiUsageEvent | None:
    """Registra um evento de uso de IA. Nunca lança exceção: falha de
    banco (ou nenhuma sessão disponível) vira `logger.warning` e `None` —
    telemetria não pode derrubar a chamada de IA real que ela registra."""
    evento = AiUsageEvent(
        origem=origem,
        ambiente=ambiente,
        modelo=modelo,
        operacao=operacao,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        custo_usd=round(custo_usd, 6),
        referencia_id=referencia_id,
    )

    try:
        if session is not None:
            session.add(evento)
            if commit:
                await session.commit()
            else:
                await session.flush()
            return evento

        factory = session_factory or _global_sessionmaker
        if factory is not None:
            async with factory() as s:
                s.add(evento)
                await s.commit()
                return evento
    except Exception as exc:
        logger.warning(
            "Falha ao registrar AiUsageEvent (origem=%s, operacao=%s): %s",
            origem,
            operacao,
            exc,
        )
    return None
```

- [ ] **Step 4: Rodar os testes para confirmar que passam**

Run: `cd backend && .venv/bin/pytest tests/test_ai_usage.py -v`
Expected: PASS (6 testes — o da Task 1 + os 5 novos)

- [ ] **Step 5: Commit**

```bash
cd backend
git add src/app/services/ai_usage.py tests/test_ai_usage.py
git commit -m "feat(telemetria): adiciona registrar_uso_ia (item A do ledger de uso de IA)"
```

---

### Task 3: Bootstrap em `app.main` + Documentação

**Files:**
- Modify: `backend/src/app/main.py:254` (logo após a linha de
  `ingestion_metrics.set_global_sessionmaker`)
- Modify: `docs/ARCHITECTURE.md` (nova entrada, decisão registrada)
- Modify: `docs/ROADMAP.md` (marcar o item A como `[x]`)

**Interfaces:**
- Consumes: `app.services.ai_usage.set_global_sessionmaker` (Task 2).

- [ ] **Step 1: Adicionar o bootstrap em `app.main`**

Em `backend/src/app/main.py`, imediatamente depois destas duas linhas já
existentes (procurar por `set_global_sessionmaker(app.state.db_sessionmaker)`):

```python
    from app.services.ingestion_metrics import set_global_sessionmaker
    set_global_sessionmaker(app.state.db_sessionmaker)
```

adicionar:

```python
    from app.services.ai_usage import set_global_sessionmaker as set_global_sessionmaker_ai
    set_global_sessionmaker_ai(app.state.db_sessionmaker)
```

(Alias de import só para não colidir com o símbolo `set_global_sessionmaker`
já importado de `ingestion_metrics` no mesmo escopo — os dois módulos têm
uma função com o mesmo nome, de propósito, por serem o mesmo padrão.)

- [ ] **Step 2: Verificar que a aplicação ainda sobe sem erro**

Run: `cd backend && .venv/bin/python -c "from app.main import app; print('OK')"`
Expected: imprime `OK` sem lançar exceção (confirma que o import novo em
`main.py` está sintaticamente correto e não quebra a criação do app).

- [ ] **Step 3: Rodar a suíte completa do backend para checar regressão**

Run: `cd backend && .venv/bin/pytest -q`
Expected: todos os testes existentes continuam passando (nenhum
comportamento observável mudou — só uma função nova e um bootstrap).

- [ ] **Step 4: Atualizar `docs/ARCHITECTURE.md`**

Adicionar uma nova entrada na seção de telemetria (próximo à entrada já
existente sobre `ConversaMensagem.metricas`/custos, por volta da linha
826 — buscar por "Correção também em 2026-10-08" para achar o ponto certo,
já que esse texto foi inserido numa correção anterior na mesma área):

```markdown
**Decisão registrada (Ledger unificado de uso de IA, 2026-10-08):** nova
tabela `ai_usage_events` (`app.db.models.AiUsageEvent`, migração `0024`)
e função central `app.services.ai_usage.registrar_uso_ia` — todo ponto do
sistema que usa um modelo/engine de IA (local ou externo, texto ou visão)
registra um evento com `origem` (chat/b2b/admin, extensível),
`ambiente` (interno/externo), `modelo`, `operacao`, tokens de
entrada/saída e custo em USD. Motivado por não ser possível, antes desta
mudança, identificar no painel `/admin/metricas` o que foi gasto em visão
computacional interna x externa — e por achados mais graves durante a
investigação: custo de visão do avaliador de comprovante nunca era
capturado (nem no fluxo de chat, nem no da ferramenta MCP B2B
`converter_reserva_venda`, que chama o mesmo avaliador), e o
classificador/monitor de tom via TypeSafe Jev nunca teve métrica alguma
capturada. Mesmo padrão de sessão (explícita / fire-and-forget / fallback
global) de `app.services.ingestion_metrics.record_ingestion_cost`,
reaproveitado de propósito. Este item (A) só entrega a fundação — nenhum
ponto de chamada real foi conectado ainda; ver
`docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md`
e os itens B/C/D/E em `docs/ROADMAP.md`.
```

- [ ] **Step 5: Marcar o item A como concluído em `docs/ROADMAP.md`**

Trocar `- [ ] **A — Fundação: ...` por `- [x] **A — Fundação: ...` na
seção "Extra fora do MVP — Ledger Unificado de Uso de IA (Origem ×
Ambiente × Modelo)" (os itens B/C/D/E continuam `- [ ]`, sem alteração).

- [ ] **Step 6: Commit**

```bash
cd backend
git add src/app/main.py
cd ..
git add docs/ARCHITECTURE.md docs/ROADMAP.md
git commit -m "feat(telemetria): conecta o sessionmaker global do ledger de uso de IA e documenta o item A"
```

---

## Self-Review (feito ao escrever este plano)

1. **Cobertura da spec:** §3.1 (tabela) → Task 1. §3.2 (migração) → Task 1.
   §4 (função central) → Task 2. §5 (6 casos de teste) → Task 1 (1º caso,
   o modelo puro) + Task 2 (5 casos restantes, a função). §6 (fora de
   escopo: nenhum ponto de chamada real, nenhuma mudança em
   `IngestionCostEvent`) → respeitado, nenhuma task toca nisso. §7
   (próximos passos 1-6) → mapeados 1:1 para as 3 tasks.
2. **Placeholders:** nenhum `TBD`/`TODO`; todo código é completo e
   executável como escrito.
3. **Consistência de tipos:** `registrar_uso_ia`'s assinatura (Task 2) é
   idêntica à usada nos testes (Task 2) e à descrita nas Interfaces de
   cada task; `AiUsageEvent` (Task 1) tem exatamente os mesmos 9 campos
   em todo lugar que aparece (spec, modelo, migração, testes).
