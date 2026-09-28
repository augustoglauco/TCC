# Monitor de Tom (R8, Fase 4B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar R8 do roadmap — monitorar o tom de cada mensagem do cliente em paralelo ao roteamento normal e, quando a urgência/insatisfação ultrapassa um limiar, emitir um alerta SSE, registrar o caso no Postgres para follow-up humano e expor uma listagem administrativa — sem interromper a resposta normal do domínio.

**Architecture:** Novo módulo puro `app.router.tone_monitor` (heurística de palavras-chave/sinais estruturais → fallback configurável entre LLM local e TypeSafe Jev via OpenRouter) roda no início de `handle_message`, em paralelo lógico à classificação de domínio (não substitui a resposta). Primeira escalada de uma conversa emite um evento SSE `escalonamento` antes do `done`, persiste um registro em `tom_escalonamentos` (Postgres) e loga um evento estruturado. Backend-only: o banner visual no frontend fica para a Fase 8 (fora de escopo desta entrega).

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 async + Alembic, pytest + pytest-asyncio, httpx (`MockTransport` para testes do OpenRouter), Ollama (`think: false` já ativo), OpenRouter `/systemone` (TypeSafe Jev).

**Spec:** `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md` — o plano abaixo argumenta a partir dela; qualquer conflito entre um passo deste plano e o texto da spec resolve-se a favor da spec.

## Global Constraints

- `ToneResult.provider_efetivo` só assume dois valores: `"heuristica_llm"` (heurística OU fallback ao LLM local — mesmo provedor configurado) e `"jev_openrouter"` (só quando o Jev respondeu de fato). Qualquer falha do Jev degrada para `"heuristica_llm"`, nunca derruba a mensagem do usuário (mesma convenção de `ClassificationResult.provider_efetivo`, docs/ARCHITECTURE.md §5).
- `ToneResult.motivo` só assume três valores: `"urgencia"`, `"insatisfacao"`, ou `None` (quando `escalate=False`).
- `TONE_MONITOR_ENABLED` default `true`; `TONE_MONITOR_PROVIDER` default `"heuristica_llm"` (valores possíveis: `"heuristica_llm"` | `"jev_openrouter"`).
- Migração Alembic desta entrega: `revision = "0006"`, `down_revision = "0005"` (a migração mais recente hoje é `0005_rag_collection_purpose.py`).
- Evento SSE novo: `event: escalonamento`, payload `{"motivo": <str|null>, "confianca": <float>}`, emitido **antes** do `done`, só na primeira escalada de cada `conversation_id` (estado em memória, mesmo padrão MVP de `booking_slots`/`_conversation_history` — perdido em restart do processo).
- Endpoint novo: `GET /api/admin/tom/escalonamentos`, `LIMIT 100` fixo, sem paginação, mais recente primeiro.
- Sem mecanismo de "des-escalar" uma conversa já marcada — `# MVP` aceito, mesmo espírito do fluxo de agendamento.
- Banner visual no frontend, fila real de atendimento humano e painel administrativo visual estão **fora de escopo** desta entrega (spec §9).

---

### Task 1: Configuração e Runtime Settings

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/src/app/models/runtime_settings.py`
- Modify: `backend/src/app/api/runtime_settings.py`
- Modify: `backend/src/app/main.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`
- Test: `backend/tests/test_runtime_settings_api.py`

**Interfaces:**
- Produces: `Settings.tone_monitor_enabled: bool` (default `True`), `Settings.tone_monitor_provider: Literal["heuristica_llm", "jev_openrouter"]` (default `"heuristica_llm"`) em `app.config`.
- Produces: `ToneMonitorProvider = Literal["heuristica_llm", "jev_openrouter"]` e `DEFAULT_TONE_MONITOR_PROVIDER: ToneMonitorProvider = "heuristica_llm"` em `app.models.runtime_settings` — consumidos pelas Tasks 4, 6 e 7.
- Produces: `app.state.tone_monitor_enabled: bool` e `app.state.tone_monitor_provider: str`, lidos/escritos via `GET`/`PUT /api/admin/runtime-settings` — consumidos pela Task 7 (`app.api.chat`).

- [ ] **Step 1: Escrever o teste que falha (config.py)**

Em `backend/tests/test_config.py`, adicionar ao final do arquivo:

```python
def test_settings_have_tone_monitor_defaults():
    settings = Settings(_env_file=None)
    assert settings.tone_monitor_enabled is True
    assert settings.tone_monitor_provider == "heuristica_llm"
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_config.py::test_settings_have_tone_monitor_defaults -v`
Expected: FAIL com `AttributeError: 'Settings' object has no attribute 'tone_monitor_enabled'`

- [ ] **Step 3: Adicionar os campos em `Settings`**

Em `backend/src/app/config.py`, logo após o bloco `jev_timeout_s` (linhas 48-53), adicionar:

```python
    # Monitor de Tom (R8, Fase 4B, além do MVP original — ver
    # docs/ARCHITECTURE.md §5, decisão 2026-09-23, e
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md). Mesmo
    # padrão de dois provedores do classificador de intenção acima
    # (heuristica_llm/jev_openrouter) — ajustável em runtime via
    # PUT /api/admin/runtime-settings (ver app/api/runtime_settings.py).
    tone_monitor_enabled: bool = True
    tone_monitor_provider: Literal["heuristica_llm", "jev_openrouter"] = "heuristica_llm"
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_config.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Adicionar o tipo e a constante em `runtime_settings.py`**

Em `backend/src/app/models/runtime_settings.py`, logo após a definição de `DEFAULT_INTENT_ROUTER_PROVIDER` (linha 15), adicionar:

```python
ToneMonitorProvider = Literal["heuristica_llm", "jev_openrouter"]
# Mesmo padrão de DEFAULT_INTENT_ROUTER_PROVIDER acima — único ponto de
# definição do default do Monitor de Tom (R8, Fase 4B).
DEFAULT_TONE_MONITOR_PROVIDER: ToneMonitorProvider = "heuristica_llm"
```

Em seguida, adicionar dois campos ao final de `RuntimeSettingsResponse` (depois de `intent_router_provider`):

```python
    tone_monitor_enabled: bool = Field(
        ..., description="Liga/desliga o Monitor de Tom (R8) — heurística e fallback nunca rodam quando false."
    )
    tone_monitor_provider: ToneMonitorProvider = Field(
        default=DEFAULT_TONE_MONITOR_PROVIDER,
        description="Provedor do fallback ambíguo do Monitor de Tom quando a heurística não encontra sinal forte.",
    )
```

E dois campos ao final de `RuntimeSettingsUpdateRequest`:

```python
    tone_monitor_enabled: bool | None = None
    tone_monitor_provider: ToneMonitorProvider | None = None
```

- [ ] **Step 6: Escrever o teste que falha (runtime_settings_api.py)**

Em `backend/tests/test_runtime_settings_api.py`, adicionar `DEFAULT_TONE_MONITOR_PROVIDER` ao import existente de `app.models.runtime_settings` (linha 5), e em `_build_app` adicionar o parâmetro `tone_monitor_enabled: bool = True, tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER` com as respectivas linhas `app.state.tone_monitor_enabled = tone_monitor_enabled` e `app.state.tone_monitor_provider = tone_monitor_provider` (mesmo padrão de `intent_router_provider` já existente na função). Depois, adicionar ao final do arquivo:

```python
def test_get_runtime_settings_traz_defaults_do_monitor_de_tom():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.get("/api/admin/runtime-settings")

    assert response.status_code == 200
    body = response.json()
    assert body["tone_monitor_enabled"] is True
    assert body["tone_monitor_provider"] == "heuristica_llm"


def test_put_runtime_settings_atualiza_monitor_de_tom():
    app, *_ = _build_default_app()
    client = TestClient(app)

    response = client.put(
        "/api/admin/runtime-settings",
        json={"tone_monitor_enabled": False, "tone_monitor_provider": "jev_openrouter"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tone_monitor_enabled"] is False
    assert body["tone_monitor_provider"] == "jev_openrouter"
```

- [ ] **Step 7: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_runtime_settings_api.py -k monitor_de_tom -v`
Expected: FAIL (campos ausentes na resposta/estado)

- [ ] **Step 8: Ler/escrever os dois novos campos em `app/api/runtime_settings.py`**

Em `backend/src/app/api/runtime_settings.py`, importar `DEFAULT_TONE_MONITOR_PROVIDER` junto de `DEFAULT_INTENT_ROUTER_PROVIDER` (linha 13). Em `_build_response`, logo após a leitura de `intent_provider` (linhas 36-38), adicionar:

```python
    tone_monitor_enabled = getattr(request.app.state, "tone_monitor_enabled", True)
    tone_monitor_provider = getattr(
        request.app.state, "tone_monitor_provider", DEFAULT_TONE_MONITOR_PROVIDER
    )
```

E no `return RuntimeSettingsResponse(...)`, adicionar as duas linhas finais:

```python
        tone_monitor_enabled=tone_monitor_enabled,
        tone_monitor_provider=tone_monitor_provider,
```

Em `update_runtime_settings`, logo após o bloco `if "intent_router_provider" in campos:` (linhas 89-90), adicionar:

```python
    if "tone_monitor_enabled" in campos:
        request.app.state.tone_monitor_enabled = campos["tone_monitor_enabled"]
    if "tone_monitor_provider" in campos:
        request.app.state.tone_monitor_provider = campos["tone_monitor_provider"]
```

- [ ] **Step 9: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_runtime_settings_api.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 10: Inicializar o estado em `main.py`**

Em `backend/src/app/main.py`, importar `DEFAULT_TONE_MONITOR_PROVIDER` junto de `DEFAULT_INTENT_ROUTER_PROVIDER` (linha 21). Logo após a linha `app.state.intent_router_provider = DEFAULT_INTENT_ROUTER_PROVIDER`, adicionar:

```python
    # Monitor de Tom (R8, Fase 4B) — diferente de intent_router_provider
    # acima, aqui o valor inicial vem de settings/env (TONE_MONITOR_ENABLED/
    # TONE_MONITOR_PROVIDER), não de uma constante fixa: a spec pede default
    # configurável por ambiente (docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §7).
    app.state.tone_monitor_enabled = settings.tone_monitor_enabled
    app.state.tone_monitor_provider = settings.tone_monitor_provider
```

- [ ] **Step 11: Documentar as duas variáveis em `.env.example`**

Em `backend/.env.example`, logo após `JEV_TIMEOUT_S=10.0`, adicionar:

```
# --- Monitor de Tom (R8, Fase 4B) ---
# Fora do MVP original, ver docs/ARCHITECTURE.md §5 (decisão 2026-09-23) e
# docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md. Mesmo padrão de
# dois provedores do classificador de intenção acima
# (heuristica_llm/jev_openrouter).
TONE_MONITOR_ENABLED=true
TONE_MONITOR_PROVIDER=heuristica_llm
```

- [ ] **Step 12: Rodar a suíte completa e commitar**

Run: `cd backend && .venv/bin/pytest tests/test_config.py tests/test_runtime_settings_api.py -v`
Expected: PASS

```bash
git add backend/src/app/config.py backend/src/app/models/runtime_settings.py \
  backend/src/app/api/runtime_settings.py backend/src/app/main.py backend/.env.example \
  backend/tests/test_config.py backend/tests/test_runtime_settings_api.py
git commit -m "feat(tom): adiciona config e runtime settings do Monitor de Tom (R8)"
```

---

### Task 2: Modelo ORM e migração `tom_escalonamentos`

**Files:**
- Modify: `backend/src/app/db/models.py`
- Create: `backend/migrations/versions/0006_tom_escalonamentos.py`
- Test: `backend/tests/test_db_models.py` (criar se não existir — ver Step 1)

**Interfaces:**
- Produces: `app.db.models.TomEscalonamento` (colunas `id: uuid.UUID`, `conversation_id: str`, `mensagem: str`, `motivo: str | None`, `confianca: float`, `provider_efetivo: str`, `criado_em: datetime`) — consumido pela Task 5 (`criar_escalonamento`/`listar_escalonamentos`).

- [ ] **Step 1: Escrever o teste que falha**

Verificar se `backend/tests/test_db_models.py` já existe (`ls backend/tests/test_db_models.py`). Se não existir, criar com este conteúdo; se existir, só adicionar a função de teste ao final:

```python
from app.db.models import Base, TomEscalonamento
from app.db.engine import create_db_engine, create_session_factory


async def test_tom_escalonamento_tem_colunas_esperadas():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)

    async with factory() as session:
        registro = TomEscalonamento(
            conversation_id="conv-1",
            mensagem="preciso falar com um atendente AGORA",
            motivo="urgencia",
            confianca=0.9,
            provider_efetivo="heuristica_llm",
        )
        session.add(registro)
        await session.commit()
        await session.refresh(registro)

        assert registro.id is not None
        assert registro.conversation_id == "conv-1"
        assert registro.criado_em is not None

    await engine.dispose()
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_db_models.py -v`
Expected: FAIL com `ImportError: cannot import name 'TomEscalonamento'`

- [ ] **Step 3: Adicionar a classe ORM**

Em `backend/src/app/db/models.py`, ao final do arquivo (depois de `CrawlerPendingPage`), adicionar:

```python


class TomEscalonamento(Base):
    """Caso de escalonamento do Monitor de Tom (R8, Fase 4B) — ver
    docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §5.

    Append-only: cada linha é o momento em que uma conversa escalou pela
    primeira vez (o estado "já escalada", que evita repetir o alerta, vive
    em memória em `app.router.tone_monitor._conversas_escaladas`, não
    nesta tabela). Sem mecanismo de "des-escalar" — decisão aceita da spec.
    """

    __tablename__ = "tom_escalonamentos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[str]
    mensagem: Mapped[str]
    motivo: Mapped[str | None]
    confianca: Mapped[float]
    provider_efetivo: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_db_models.py -v`
Expected: PASS

- [ ] **Step 5: Criar a migração Alembic**

Criar `backend/migrations/versions/0006_tom_escalonamentos.py`:

```python
"""tom_escalonamentos (Monitor de Tom, R8, Fase 4B)

Ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §5. Tabela
append-only — sem coluna de atualização, cada linha é uma escalada.

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tom_escalonamentos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("mensagem", sa.String(), nullable=False),
        sa.Column("motivo", sa.String(), nullable=True),
        sa.Column("confianca", sa.Float(), nullable=False),
        sa.Column("provider_efetivo", sa.String(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("tom_escalonamentos")
```

- [ ] **Step 6: Validar a migração contra um Postgres real (se disponível neste ambiente)**

Run: `cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic downgrade -1 && .venv/bin/alembic upgrade head`
Expected: os três comandos rodam sem erro. Se não houver Postgres no ar neste ambiente (`could not connect to server`), pule este passo e registre no relatório da task — a Task 9 (verificação E2E) repete esta checagem com a infraestrutura completa no ar.

- [ ] **Step 7: Commitar**

```bash
git add backend/src/app/db/models.py backend/migrations/versions/0006_tom_escalonamentos.py backend/tests/test_db_models.py
git commit -m "feat(tom): adiciona modelo e migração da tabela tom_escalonamentos (R8)"
```

---

### Task 3: `OpenRouterClient.classify_tone_jev`

**Files:**
- Modify: `backend/src/app/router/openrouter_client.py`
- Test: `backend/tests/test_openrouter_client.py`

**Interfaces:**
- Produces: `OpenRouterClient.classify_tone_jev(message: str, recent_messages: list[str] | None = None) -> tuple[bool, float]` — consumido pela Task 4 (`tone_monitor._analyze_with_jev`).

- [ ] **Step 1: Escrever os testes que falham**

Em `backend/tests/test_openrouter_client.py`, ao final do arquivo, adicionar:

```python
@pytest.mark.asyncio
async def test_classify_tone_jev_noul_alto_escala():
    captured_request: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_request["url"] = str(request.url)
        captured_request["body"] = json.loads(request.content)
        data = {"answers": {"escalar": {"type": "noul", "noul": 0.92}}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        escalate, confidence = await client.classify_tone_jev(
            message="Ninguém me ajuda, preciso falar com um atendente agora!",
            recent_messages=[],
        )
        assert escalate is True
        assert confidence == 0.92
        assert captured_request["url"].endswith("/systemone")
        body = captured_request["body"]
        assert body["model"] == "typesafe/jev-latest"
        assert body["questions"]["escalar"]["type"] == "noul"


@pytest.mark.asyncio
async def test_classify_tone_jev_noul_baixo_nao_escala():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        data = {"answers": {"escalar": {"type": "noul", "noul": 0.1}}}
        return httpx.Response(200, json=data)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        escalate, confidence = await client.classify_tone_jev(
            message="Só queria saber o horário de funcionamento.", recent_messages=[]
        )
        assert escalate is False
        assert confidence == 0.1


@pytest.mark.asyncio
async def test_classify_tone_jev_falha_http_propaga_excecao():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as mock_client:
        client = OpenRouterClient(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="meta-llama/llama-3",
            timeout_s=5.0,
            client=mock_client,
            jev_model="typesafe/jev-latest",
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.classify_tone_jev(message="teste", recent_messages=[])
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_openrouter_client.py -k classify_tone_jev -v`
Expected: FAIL com `AttributeError: 'OpenRouterClient' object has no attribute 'classify_tone_jev'`

- [ ] **Step 3: Implementar `classify_tone_jev`**

Em `backend/src/app/router/openrouter_client.py`, ao final do arquivo (depois de `classify_intent_jev`), adicionar:

```python

    async def classify_tone_jev(
        self, message: str, recent_messages: list[str] | None = None
    ) -> tuple[bool, float]:
        """Avalia urgência/insatisfação via TypeSafe Jev (R8, Fase 4B) —
        mesmo endpoint dedicado de `classify_intent_jev` (`/systemone`), mas
        com uma pergunta do tipo `noul` (sim/não com probabilidade
        calibrada) em vez de `choice` — ver
        docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3.2.
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
                    "escalar": {
                        "type": "noul",
                        "instructions": (
                            "O cliente está demonstrando urgência ou insatisfação forte "
                            "que justifique transferência para atendimento humano?"
                        ),
                        "criteria": {
                            "true": (
                                "Mensagem com tom de urgência, raiva, ameaça de "
                                "cancelamento/processo, ou insatisfação explícita e forte."
                            ),
                            "false": (
                                "Tom neutro ou normal de atendimento, mesmo com dúvida "
                                "ou reclamação leve."
                            ),
                        },
                    }
                },
            },
            timeout=self._jev_timeout_s,
        )
        response.raise_for_status()
        noul = float(response.json()["answers"]["escalar"]["noul"])
        return noul >= 0.5, noul
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_openrouter_client.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commitar**

```bash
git add backend/src/app/router/openrouter_client.py backend/tests/test_openrouter_client.py
git commit -m "feat(tom): adiciona OpenRouterClient.classify_tone_jev (R8)"
```

---

### Task 4: `app/router/tone_monitor.py` — heurística, `analyze_tone` e estado de conversa

**Files:**
- Create: `backend/src/app/router/tone_monitor.py`
- Test: `backend/tests/test_tone_monitor.py`

**Interfaces:**
- Consumes: `app.router.classifier._normalize(text: str) -> str`; `app.router.classifier._strip_code_fence(text: str) -> str`; `app.router.llm_client.LLMClient` (`async def generate(prompt: str) -> LLMResponse`); `OpenRouterClient.classify_tone_jev(message, recent_messages) -> tuple[bool, float]` (Task 3).
- Produces: `ToneResult(BaseModel)` com `escalate: bool`, `motivo: str | None`, `confidence: float`, `provider_efetivo: str`. `async def analyze_tone(message: str, recent_messages: list[str], strategy_provider: str, llm_client: LLMClient, external_client: Any) -> ToneResult`. `marcar_escalada(conversation_id: str) -> None`, `ja_escalada(conversation_id: str) -> bool`, `reset_escalated_conversations() -> None` — todos consumidos pela Task 6 (`orchestrator.handle_message`).

- [ ] **Step 1: Escrever os testes que falham**

Criar `backend/tests/test_tone_monitor.py`:

```python
import pytest

from app.router.llm_client import LLMResponse
from app.router.tone_monitor import (
    ToneResult,
    analyze_tone,
    ja_escalada,
    marcar_escalada,
    reset_escalated_conversations,
)


class _FakeLLMClient:
    def __init__(self, response: LLMResponse | None = None, exception: Exception | None = None) -> None:
        self._response = response
        self._exception = exception
        self.prompts: list[str] = []

    async def generate(self, prompt: str) -> LLMResponse:
        self.prompts.append(prompt)
        if self._exception is not None:
            raise self._exception
        assert self._response is not None
        return self._response


class _FakeJevClient:
    def __init__(self, escalate: bool = False, confidence: float = 0.0, exception: Exception | None = None) -> None:
        self._escalate = escalate
        self._confidence = confidence
        self._exception = exception

    async def classify_tone_jev(self, message: str, recent_messages: list[str] | None = None):
        if self._exception is not None:
            raise self._exception
        return self._escalate, self._confidence


@pytest.mark.asyncio
async def test_heuristica_palavra_chave_de_insatisfacao_escala_sem_chamar_llm():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="Isso é um absurdo, nunca mais compro nessa loja",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "insatisfacao"
    assert resultado.provider_efetivo == "heuristica_llm"
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_heuristica_maiusculas_e_exclamacao_escala_como_urgencia():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="PRECISO FALAR COM ALGUEM AGORA!!!",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "urgencia"
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_mensagem_neutra_cai_no_fallback_llm_local():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": false, "motivo": null, "confianca": 0.1}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Qual o horário de funcionamento da loja?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.motivo is None
    assert resultado.provider_efetivo == "heuristica_llm"
    assert len(llm.prompts) == 1


@pytest.mark.asyncio
async def test_fallback_llm_escala_quando_modelo_reporta_true():
    llm = _FakeLLMClient(
        LLMResponse(
            text='{"escalar": true, "motivo": "urgencia", "confianca": 0.8}', total_duration_ms=5.0
        )
    )
    resultado = await analyze_tone(
        message="Isso está demorando muito, quando vai resolver?",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is True
    assert resultado.motivo == "urgencia"
    assert resultado.confidence == 0.8


@pytest.mark.asyncio
async def test_fallback_llm_resposta_nao_parseavel_nao_escala():
    llm = _FakeLLMClient(LLMResponse(text="não é json", total_duration_ms=5.0))
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="heuristica_llm",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


@pytest.mark.asyncio
async def test_fallback_jev_sucesso_usa_provider_jev_openrouter():
    llm = _FakeLLMClient()
    jev = _FakeJevClient(escalate=True, confidence=0.9)
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=jev,
    )
    assert resultado.escalate is True
    assert resultado.provider_efetivo == "jev_openrouter"
    assert resultado.confidence == 0.9
    assert llm.prompts == []


@pytest.mark.asyncio
async def test_fallback_jev_falha_degrada_para_heuristica_llm_sem_escalar():
    llm = _FakeLLMClient()
    jev = _FakeJevClient(exception=TimeoutError("timeout"))
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=jev,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


@pytest.mark.asyncio
async def test_fallback_jev_sem_client_valido_degrada():
    llm = _FakeLLMClient()
    resultado = await analyze_tone(
        message="Mensagem ambígua qualquer",
        recent_messages=[],
        strategy_provider="jev_openrouter",
        llm_client=llm,
        external_client=None,
    )
    assert resultado.escalate is False
    assert resultado.provider_efetivo == "heuristica_llm"


def test_estado_de_conversa_marcar_e_consultar_escalada():
    reset_escalated_conversations()
    assert ja_escalada("conv-1") is False
    marcar_escalada("conv-1")
    assert ja_escalada("conv-1") is True
    assert ja_escalada("conv-2") is False
    reset_escalated_conversations()
    assert ja_escalada("conv-1") is False
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_tone_monitor.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.router.tone_monitor'`

- [ ] **Step 3: Implementar `tone_monitor.py`**

Criar `backend/src/app/router/tone_monitor.py`:

```python
import json
import logging
from typing import Any

from pydantic import BaseModel

from app.models.runtime_settings import DEFAULT_TONE_MONITOR_PROVIDER
from app.router.classifier import _normalize, _strip_code_fence
from app.router.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ToneResult(BaseModel):
    escalate: bool
    motivo: str | None  # "urgencia" | "insatisfacao" | None quando escalate=False
    confidence: float
    # Mesma convenção de ClassificationResult.provider_efetivo
    # (docs/ARCHITECTURE.md §5): só distingue qual dos DOIS provedores
    # configuráveis (TONE_MONITOR_PROVIDER) decidiu de fato — falha do Jev
    # sempre degrada para "heuristica_llm", nunca derruba a mensagem do
    # usuário (ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3).
    provider_efetivo: str = DEFAULT_TONE_MONITOR_PROVIDER


# MVP: heurística simples de palavras-chave, mesmo espírito de
# app.router.classifier._DOMAIN_KEYWORDS — sem NLP mais robusto, lista a
# refinar contra casos reais quando existirem.
_URGENCIA_KEYWORDS = ["urgente", "agora mesmo", "imediatamente"]
_INSATISFACAO_KEYWORDS = [
    "pessimo",
    "absurdo",
    "cancelar tudo",
    "processar",
    "reclamacao procon",
    "nunca mais compro",
]

_UPPERCASE_ALPHA_MIN = 10
_UPPERCASE_RATIO_THRESHOLD = 0.7
_EXCLAMATION_RUN_MIN = 3


def _match_keyword_signal(message: str) -> str | None:
    normalized = _normalize(message)
    if any(k in normalized for k in _URGENCIA_KEYWORDS):
        return "urgencia"
    if any(k in normalized for k in _INSATISFACAO_KEYWORDS):
        return "insatisfacao"
    return None


def _match_structural_signal(message: str) -> str | None:
    # Sinal estrutural (maiúsculas/pontuação) lido como urgência — não há
    # como a pontuação por si só distinguir insatisfação de urgência, ver
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3.1.
    alpha_chars = [c for c in message if c.isalpha()]
    if len(alpha_chars) >= _UPPERCASE_ALPHA_MIN:
        uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if uppercase_ratio >= _UPPERCASE_RATIO_THRESHOLD:
            return "urgencia"
    if "!" * _EXCLAMATION_RUN_MIN in message:
        return "urgencia"
    return None


def _match_heuristic_signal(message: str) -> str | None:
    return _match_keyword_signal(message) or _match_structural_signal(message)


_TONE_PROMPT_TEMPLATE = """\
Avalie se a mensagem do cliente abaixo demonstra urgência ou insatisfação \
forte o suficiente para justificar transferência a um atendente humano.

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"escalar": true|false, "motivo": "urgencia"|"insatisfacao"|null, "confianca": 0.0}}"""


async def _analyze_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ToneResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _TONE_PROMPT_TEMPLATE.format(contexto=contexto, mensagem=message)
    try:
        response = await llm_client.generate(prompt)
        parsed = json.loads(_strip_code_fence(response.text))
        escalate = bool(parsed.get("escalar", False))
        motivo = parsed.get("motivo") if escalate else None
        confidence = float(parsed.get("confianca", 0.0))
        return ToneResult(
            escalate=escalate,
            motivo=motivo,
            confidence=confidence,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        # Resposta não-parseável: ambíguo sem sinal claro não escala por
        # padrão, lado seguro contra falso positivo (mesmo espírito de
        # classifier._classify_heuristic_fallback).
        return ToneResult(
            escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
        )


async def _analyze_with_jev(
    message: str, recent_messages: list[str], external_client: Any
) -> ToneResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_tone_jev"):
            raise ValueError("external_client inválido para Jev")
        escalate, confidence = await external_client.classify_tone_jev(message, recent_messages)
        # Jev responde com uma única pergunta noul (sim/não) — não distingue
        # motivo. "insatisfacao" é um rótulo genérico quando escala; refinar
        # com duas perguntas noul separadas fica para uma iteração futura.
        return ToneResult(
            escalate=escalate,
            motivo="insatisfacao" if escalate else None,
            confidence=confidence,
            provider_efetivo="jev_openrouter",
        )
    except Exception as exc:
        logger.warning(
            "jev_tom_falhou_fallback_heuristica",
            extra={"router": {"event": "jev_tom_falha_fallback", "erro": str(exc)}},
        )
        return ToneResult(
            escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
        )


async def analyze_tone(
    message: str,
    recent_messages: list[str],
    strategy_provider: str,
    llm_client: LLMClient,
    external_client: Any,
) -> ToneResult:
    sinal = _match_heuristic_signal(message)
    if sinal is not None:
        return ToneResult(
            escalate=True,
            motivo=sinal,
            confidence=1.0,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )

    if strategy_provider == "jev_openrouter":
        return await _analyze_with_jev(message, recent_messages, external_client)

    return await _analyze_with_llm(message, recent_messages, llm_client)


# MVP: estado em memória por processo, mesmo padrão de
# app.router.scheduling.booking_slots e app.api.chat._conversation_history —
# perdido em restart do processo, sem mecanismo de "des-escalar" (decisão
# aceita da spec §2).
_conversas_escaladas: set[str] = set()


def marcar_escalada(conversation_id: str) -> None:
    _conversas_escaladas.add(conversation_id)


def ja_escalada(conversation_id: str) -> bool:
    return conversation_id in _conversas_escaladas


def reset_escalated_conversations() -> None:
    """Limpa o estado em memória — usado pelos testes para isolar casos."""
    _conversas_escaladas.clear()
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_tone_monitor.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commitar**

```bash
git add backend/src/app/router/tone_monitor.py backend/tests/test_tone_monitor.py
git commit -m "feat(tom): adiciona classificação de tom (heurística + fallback LLM/Jev) (R8)"
```

---

### Task 5: Persistência — `criar_escalonamento`/`listar_escalonamentos`

**Files:**
- Modify: `backend/src/app/router/tone_monitor.py`
- Test: `backend/tests/test_tone_monitor.py`

**Interfaces:**
- Consumes: `app.db.models.TomEscalonamento` (Task 2).
- Produces: `async def criar_escalonamento(session: AsyncSession, *, conversation_id: str, mensagem: str, motivo: str | None, confianca: float, provider_efetivo: str) -> TomEscalonamento`; `async def listar_escalonamentos(session: AsyncSession, limit: int = 100) -> list[TomEscalonamento]` — consumidos pela Task 7 (`app.api.chat`) e Task 8 (`app.api.tom_escalonamentos`).

- [ ] **Step 1: Escrever os testes que falham**

Em `backend/tests/test_tone_monitor.py`, adicionar ao topo do import existente `from app.router.tone_monitor import (...)` os novos nomes `criar_escalonamento` e `listar_escalonamentos`, e ao final do arquivo:

```python
async def test_criar_escalonamento_persiste_e_retorna_o_registro(db_session):
    registro = await criar_escalonamento(
        db_session,
        conversation_id="conv-1",
        mensagem="preciso falar com um atendente AGORA",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )

    assert registro.id is not None
    assert registro.conversation_id == "conv-1"
    assert registro.motivo == "urgencia"


async def test_listar_escalonamentos_ordena_mais_recente_primeiro(db_session):
    import asyncio

    await criar_escalonamento(
        db_session,
        conversation_id="conv-a",
        mensagem="primeira",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    await asyncio.sleep(1.1)  # garante precisão de segundo diferente no SQLite
    await criar_escalonamento(
        db_session,
        conversation_id="conv-b",
        mensagem="segunda",
        motivo="insatisfacao",
        confianca=0.8,
        provider_efetivo="jev_openrouter",
    )

    resultado = await listar_escalonamentos(db_session)

    assert [r.conversation_id for r in resultado] == ["conv-b", "conv-a"]


async def test_listar_escalonamentos_respeita_limit(db_session):
    for i in range(3):
        await criar_escalonamento(
            db_session,
            conversation_id=f"conv-{i}",
            mensagem="msg",
            motivo="urgencia",
            confianca=0.5,
            provider_efetivo="heuristica_llm",
        )

    resultado = await listar_escalonamentos(db_session, limit=2)

    assert len(resultado) == 2
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_tone_monitor.py -k escalonamento -v`
Expected: FAIL com `ImportError: cannot import name 'criar_escalonamento'`

- [ ] **Step 3: Implementar as funções de persistência**

Em `backend/src/app/router/tone_monitor.py`, adicionar os imports no topo do arquivo (junto dos existentes):

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TomEscalonamento
```

E ao final do arquivo (depois de `reset_escalated_conversations`):

```python


async def criar_escalonamento(
    session: AsyncSession,
    *,
    conversation_id: str,
    mensagem: str,
    motivo: str | None,
    confianca: float,
    provider_efetivo: str,
) -> TomEscalonamento:
    registro = TomEscalonamento(
        conversation_id=conversation_id,
        mensagem=mensagem,
        motivo=motivo,
        confianca=confianca,
        provider_efetivo=provider_efetivo,
    )
    session.add(registro)
    await session.commit()
    await session.refresh(registro)
    return registro


async def listar_escalonamentos(session: AsyncSession, limit: int = 100) -> list[TomEscalonamento]:
    result = await session.execute(
        select(TomEscalonamento).order_by(TomEscalonamento.criado_em.desc()).limit(limit)
    )
    return list(result.scalars().all())
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_tone_monitor.py -v`
Expected: PASS (todos os testes do arquivo, incluindo os da Task 4)

- [ ] **Step 5: Commitar**

```bash
git add backend/src/app/router/tone_monitor.py backend/tests/test_tone_monitor.py
git commit -m "feat(tom): adiciona persistência de escalonamentos (R8)"
```

---

### Task 6: Wiring no `orchestrator.py` — `EscalonamentoEvent`

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Test: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `app.router.tone_monitor.analyze_tone`, `.ja_escalada`, `.marcar_escalada` (Task 4); `app.models.runtime_settings.DEFAULT_TONE_MONITOR_PROVIDER` (Task 1).
- Produces: `EscalonamentoEvent(BaseModel)` com `motivo: str | None`, `confianca: float`, `provider_efetivo: str`. `handle_message(..., tone_monitor_enabled: bool = True, tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER)` agora pode `yield EscalonamentoEvent` — consumido pela Task 7 (`app.api.chat`).

- [ ] **Step 1: Escrever os testes que falham**

Em `backend/tests/test_orchestrator.py`, adicionar `EscalonamentoEvent` ao import existente de `app.router.orchestrator` (linha 11-18) e `reset_escalated_conversations` a um novo import `from app.router.tone_monitor import reset_escalated_conversations`. Adicionar ao final do arquivo:

```python
async def test_mensagem_com_sinal_forte_emite_escalonamento_alem_do_fluxo_normal():
    reset_escalated_conversations()
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"domain": "suporte", "complexity": "baixa", "confidence": 0.9}',
            total_duration_ms=1.0,
        )
    )
    external_client = _FakeLLMClient(response=LLMResponse(text="resposta externa", total_duration_ms=1.0))
    rag_client = _FakeRAGClient(documents=[Document(content="doc", source="manual", score=0.9)])

    eventos = [
        e
        async for e in handle_message(
            message="Isso é um absurdo, nunca mais compro nessa loja!",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
            conversation_id="conv-tom-1",
        )
    ]

    escalonamentos = [e for e in eventos if isinstance(e, EscalonamentoEvent)]
    decisoes = [e for e in eventos if isinstance(e, RouterDecision)]
    assert len(escalonamentos) == 1
    assert escalonamentos[0].motivo == "insatisfacao"
    assert escalonamentos[0].provider_efetivo == "heuristica_llm"
    assert len(decisoes) == 1  # fluxo normal do domínio continua rodando


async def test_segunda_mensagem_na_mesma_conversa_nao_repete_escalonamento():
    reset_escalated_conversations()
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"domain": "suporte", "complexity": "baixa", "confidence": 0.9}',
            total_duration_ms=1.0,
        )
    )
    external_client = _FakeLLMClient(response=LLMResponse(text="resposta externa", total_duration_ms=1.0))
    rag_client = _FakeRAGClient(documents=[Document(content="doc", source="manual", score=0.9)])

    async for _ in handle_message(
        message="Isso é um absurdo, nunca mais compro nessa loja!",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
        conversation_id="conv-tom-2",
    ):
        pass

    eventos_segunda_mensagem = [
        e
        async for e in handle_message(
            message="Ainda é um absurdo, processar vocês é a única saída",
            recent_messages=["Isso é um absurdo, nunca mais compro nessa loja!"],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
            conversation_id="conv-tom-2",
        )
    ]

    escalonamentos = [e for e in eventos_segunda_mensagem if isinstance(e, EscalonamentoEvent)]
    assert escalonamentos == []


async def test_tone_monitor_desligado_nunca_emite_escalonamento():
    reset_escalated_conversations()
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"domain": "suporte", "complexity": "baixa", "confidence": 0.9}',
            total_duration_ms=1.0,
        )
    )
    external_client = _FakeLLMClient(response=LLMResponse(text="resposta externa", total_duration_ms=1.0))
    rag_client = _FakeRAGClient(documents=[Document(content="doc", source="manual", score=0.9)])

    eventos = [
        e
        async for e in handle_message(
            message="Isso é um absurdo, nunca mais compro nessa loja!",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
            conversation_id="conv-tom-3",
            tone_monitor_enabled=False,
        )
    ]

    escalonamentos = [e for e in eventos if isinstance(e, EscalonamentoEvent)]
    assert escalonamentos == []
```

Verificar se `_FakeRAGClient`/`Document` já estão importados em `test_orchestrator.py` (linha 20: `from app.router.rag_client import Document, RAGConnectionError`) — se `_FakeRAGClient` não existir como classe auxiliar no arquivo, adicionar antes dos novos testes:

```python
class _FakeRAGClient:
    def __init__(self, documents: list[Document] | None = None) -> None:
        self._documents = documents if documents is not None else []

    async def search(self, query: str, domain: str) -> list[Document]:
        return self._documents
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_orchestrator.py -k escalonamento -v`
Expected: FAIL com `ImportError: cannot import name 'EscalonamentoEvent'`

- [ ] **Step 3: Adicionar `EscalonamentoEvent` e o wiring em `handle_message`**

Em `backend/src/app/router/orchestrator.py`, adicionar os imports no topo (junto dos existentes):

```python
from app.models.runtime_settings import DEFAULT_TONE_MONITOR_PROVIDER
from app.router.tone_monitor import analyze_tone, ja_escalada, marcar_escalada
```

Logo após a classe `TokenEvent` (linhas 108-109), adicionar:

```python


class EscalonamentoEvent(BaseModel):
    motivo: str | None
    confianca: float
    provider_efetivo: str
```

Alterar a assinatura de `handle_message` (linhas 344-354) adicionando dois parâmetros ao final e atualizando o tipo de retorno:

```python
async def handle_message(
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    conversation_id: str = "",
    calendar_client: CalendarClient | None = None,
    scheduling_config: SchedulingConfig | None = None,
    intent_router_provider: str = DEFAULT_INTENT_ROUTER_PROVIDER,
    tone_monitor_enabled: bool = True,
    tone_monitor_provider: str = DEFAULT_TONE_MONITOR_PROVIDER,
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision | EscalonamentoEvent]:
```

Logo no início do corpo de `handle_message` — a primeira linha executável, antes do `try:` do bloco de classificação (linha 361) — inserir:

```python
    # Monitor de Tom (R8, Fase 4B) — roda antes da classificação de
    # domínio, transversal a todo domínio (ver
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §2). Nunca
    # substitui a resposta normal: só adiciona um evento a mais no stream.
    if tone_monitor_enabled:
        tone_result = await analyze_tone(
            message=message,
            recent_messages=recent_messages,
            strategy_provider=tone_monitor_provider,
            llm_client=local_client,
            external_client=external_client,
        )
        if tone_result.escalate and not ja_escalada(conversation_id):
            marcar_escalada(conversation_id)
            yield EscalonamentoEvent(
                motivo=tone_result.motivo,
                confianca=tone_result.confidence,
                provider_efetivo=tone_result.provider_efetivo,
            )

```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_orchestrator.py -v`
Expected: PASS (todos os testes do arquivo — inclusive os pré-existentes, que agora passam `tone_monitor_enabled=True` implícito por padrão; conferir que nenhum teste antigo quebrou por causa disso)

- [ ] **Step 5: Se algum teste pré-existente quebrar por causa do Monitor de Tom ligado por padrão**

Alguns testes pré-existentes de `test_orchestrator.py` usam mensagens que podem coincidir por acaso com um sinal heurístico forte (ex.: muita pontuação/maiúsculas em um texto de teste). Se isso acontecer, ajustar a mensagem usada nesse teste específico para um texto neutro equivalente — não desligar o Monitor de Tom nos testes existentes só para "fazer passar", a menos que o teste em questão exista especificamente para validar um comportamento que o Monitor de Tom não deveria interferir (nesse caso, passar `tone_monitor_enabled=False` explicitamente nesse teste, com um comentário curto explicando o motivo).

- [ ] **Step 6: Commitar**

```bash
git add backend/src/app/router/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(tom): integra Monitor de Tom ao handle_message via EscalonamentoEvent (R8)"
```

---

### Task 7: Wiring no `chat.py` — evento SSE, persistência, log e documentação

**Files:**
- Modify: `backend/src/app/api/chat.py`
- Modify: `docs/FRONTEND.md`
- Test: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `app.router.orchestrator.EscalonamentoEvent` (Task 6); `app.router.tone_monitor.criar_escalonamento` (Task 5); `app.api.rag_dependencies.get_db_session`; `app.models.runtime_settings.DEFAULT_TONE_MONITOR_PROVIDER` (Task 1).
- Produces: dependências `get_tone_monitor_enabled(request) -> bool`, `get_tone_monitor_provider(request) -> str` em `app.api.chat` (mesmo padrão de `get_intent_router_provider`); evento SSE `escalonamento` no stream de `POST /api/chat/messages`.

- [ ] **Step 1: Escrever os testes que falham**

Em `backend/tests/test_chat_api.py`, adicionar `get_db_session` ao import de `app.api.rag_dependencies` (novo import) e `EscalonamentoEvent` não precisa ser importado no teste (só verificado via SSE). Alterar a fixture `fakes` (linha 138-150) para depender de `db_session`:

```python
@pytest.fixture
def fakes(db_session):
    return {
        "local": _FakeLLMClient(LLMResponse(text="resposta local", total_duration_ms=10.0)),
        "external": _FakeLLMClient(LLMResponse(text="resposta externa", total_duration_ms=20.0)),
        "rag": _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)]),
        "stt": _FakeSttClient(text=""),
        "clip_store": _FakeClipStore(results=[]),
        "clip_embedder": object(),
        "db_session": db_session,
    }
```

Em `_build_app` (linha 153-175), adicionar o import `from app.api.rag_dependencies import get_db_session` ao topo do arquivo e, dentro da função, adicionar:

```python
    app.dependency_overrides[get_db_session] = lambda: fakes["db_session"]
```

E ao final do arquivo, adicionar:

```python
def test_mensagem_com_sinal_forte_emite_evento_escalonamento_antes_do_done(client):
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    response = client.post(
        "/api/chat/messages",
        json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" in tipos
    assert tipos.index("escalonamento") < tipos.index("done")
    escalonamento = _find(eventos, "escalonamento")
    assert escalonamento["motivo"] == "insatisfacao"
    assert isinstance(escalonamento["confianca"], float)


def test_mensagem_neutra_nao_emite_evento_escalonamento(client):
    from app.router.tone_monitor import reset_escalated_conversations

    reset_escalated_conversations()
    response = client.post(
        "/api/chat/messages", json={"message": "Qual o horário de funcionamento?"}
    )

    assert response.status_code == 200
    eventos = _parse_sse(response.text)
    tipos = [tipo for tipo, _ in eventos]
    assert "escalonamento" not in tipos


async def test_escalonamento_e_persistido_no_banco(fakes):
    from app.router.tone_monitor import listar_escalonamentos, reset_escalated_conversations

    reset_escalated_conversations()
    app = _build_app(fakes)
    with TestClient(app) as client:
        response = client.post(
            "/api/chat/messages",
            json={"message": "Isso é um absurdo, nunca mais compro nessa loja!"},
        )
    assert response.status_code == 200

    # Teste assíncrono (em vez de asyncio.run() isolado): reaproveita o
    # mesmo loop gerenciado pelo pytest-asyncio da fixture `db_session`,
    # evitando abrir um segundo loop independente para consultar a MESMA
    # sessão SQLite em memória usada pela requisição acima.
    registros = await listar_escalonamentos(fakes["db_session"])
    assert len(registros) == 1
    assert registros[0].motivo == "insatisfacao"
    assert registros[0].provider_efetivo == "heuristica_llm"
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_chat_api.py -k escalonamento -v`
Expected: FAIL (evento `escalonamento` nunca aparece / `get_db_session` não usado ainda)

- [ ] **Step 3: Adicionar as dependências e o wiring em `chat.py`**

Em `backend/src/app/api/chat.py`, atualizar os imports:

```python
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.models.runtime_settings import DEFAULT_INTENT_ROUTER_PROVIDER, DEFAULT_TONE_MONITOR_PROVIDER
from app.router.orchestrator import (
    EscalonamentoEvent,
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.tone_monitor import criar_escalonamento
```

Logo após `get_intent_router_provider` (linhas 71-72), adicionar:

```python
def get_tone_monitor_enabled(request: Request) -> bool:
    return getattr(request.app.state, "tone_monitor_enabled", True)


def get_tone_monitor_provider(request: Request) -> str:
    return getattr(request.app.state, "tone_monitor_provider", DEFAULT_TONE_MONITOR_PROVIDER)
```

Na assinatura de `send_message` (linhas 100-113), adicionar três parâmetros ao final:

```python
    tone_monitor_enabled: bool = Depends(get_tone_monitor_enabled),
    tone_monitor_provider: str = Depends(get_tone_monitor_provider),
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
```

Na chamada a `handle_message` dentro de `event_stream()` (linhas 262-273), adicionar os dois parâmetros novos:

```python
            async for event in handle_message(
                message=effective_message,
                recent_messages=recent_messages,
                local_client=local_client,
                external_client=external_client,
                rag_client=rag_client,
                complexity_strategy=complexity_strategy,
                conversation_id=conversation_id,
                calendar_client=calendar_client,
                scheduling_config=scheduling_config,
                intent_router_provider=intent_router_provider,
                tone_monitor_enabled=tone_monitor_enabled,
                tone_monitor_provider=tone_monitor_provider,
            ):
```

E, no laço `if isinstance(event, StatusEvent): ... elif isinstance(event, TokenEvent): ... elif isinstance(event, RouterDecision): ...` (linhas 274-301), adicionar um novo ramo antes do `elif isinstance(event, RouterDecision):`:

```python
                elif isinstance(event, EscalonamentoEvent):
                    yield _sse(
                        "escalonamento", {"motivo": event.motivo, "confianca": event.confianca}
                    )
                    logger.info(
                        "tom_escalonado",
                        extra={
                            "router": {
                                "event": "tom_escalonado",
                                "conversation_id": conversation_id,
                                "motivo": event.motivo,
                                "confianca": event.confianca,
                                "provider_efetivo": event.provider_efetivo,
                            }
                        },
                    )
                    await criar_escalonamento(
                        session,
                        conversation_id=conversation_id,
                        mensagem=effective_message,
                        motivo=event.motivo,
                        confianca=event.confianca,
                        provider_efetivo=event.provider_efetivo,
                    )
```

- [ ] **Step 4: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_chat_api.py -v`
Expected: PASS (todos os testes do arquivo, incluindo os pré-existentes — a fixture `fakes`/`_build_app` foi ajustada no Step 1, então nenhum teste antigo deveria precisar de outra mudança)

- [ ] **Step 5: Documentar o evento SSE em `docs/FRONTEND.md`**

Em `docs/FRONTEND.md`, no bloco de exemplo dos eventos SSE (Seção 4), inserir um novo bloco `event: escalonamento` logo **antes** do comentário `event: done` (linha 204), assim:

```
event: escalonamento         // opcional, no máximo uma vez por conversation_id — Monitor de Tom (R8)
data: {"motivo": "urgencia", "confianca": 0.87}
// motivo: "urgencia" | "insatisfacao". Emitido quando o Monitor de Tom
// (heurística + fallback heuristica_llm/jev_openrouter, ver
// docs/ARCHITECTURE.md §5) detecta urgência/insatisfação forte na mensagem
// atual — não substitui a resposta normal do domínio, que continua sendo
// gerada e streamada. Só dispara uma vez por conversa (estado em memória
// por processo, perdido em restart). O caso também é persistido em
// `tom_escalonamentos` (Postgres) e exposto para consulta manual em
// GET /api/admin/tom/escalonamentos.

event: done                  // sempre o último evento em caso de sucesso — telemetria completa
```

- [ ] **Step 6: Commitar**

```bash
git add backend/src/app/api/chat.py backend/tests/test_chat_api.py docs/FRONTEND.md
git commit -m "feat(tom): emite evento SSE escalonamento e persiste o caso (R8)"
```

---

### Task 8: Endpoint `GET /api/admin/tom/escalonamentos`

**Files:**
- Create: `backend/src/app/models/tom_escalonamentos.py`
- Create: `backend/src/app/api/tom_escalonamentos.py`
- Modify: `backend/src/app/main.py`
- Test: `backend/tests/test_tom_escalonamentos_api.py`

**Interfaces:**
- Consumes: `app.router.tone_monitor.listar_escalonamentos` (Task 5); `app.api.rag_dependencies.get_db_session`.
- Produces: `EscalonamentoResponse(BaseModel)`; rota `GET /api/admin/tom/escalonamentos -> list[EscalonamentoResponse]`.

- [ ] **Step 1: Escrever o teste que falha**

Criar `backend/tests/test_tom_escalonamentos_api.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rag_dependencies import get_db_session
from app.api.tom_escalonamentos import router as tom_escalonamentos_router
from app.router.tone_monitor import criar_escalonamento


def _build_app(db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(tom_escalonamentos_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


def test_get_escalonamentos_vazio_quando_nao_ha_casos(db_session):
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_escalonamentos_retorna_caso_persistido(db_session):
    await criar_escalonamento(
        db_session,
        conversation_id="conv-1",
        mensagem="preciso falar com um atendente AGORA",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["conversation_id"] == "conv-1"
    assert body[0]["motivo"] == "urgencia"
    assert body[0]["provider_efetivo"] == "heuristica_llm"


async def test_get_escalonamentos_ordena_mais_recente_primeiro(db_session):
    import asyncio

    await criar_escalonamento(
        db_session,
        conversation_id="conv-a",
        mensagem="primeira",
        motivo="urgencia",
        confianca=0.9,
        provider_efetivo="heuristica_llm",
    )
    await asyncio.sleep(1.1)
    await criar_escalonamento(
        db_session,
        conversation_id="conv-b",
        mensagem="segunda",
        motivo="insatisfacao",
        confianca=0.8,
        provider_efetivo="jev_openrouter",
    )
    client = TestClient(_build_app(db_session))

    response = client.get("/api/admin/tom/escalonamentos")

    body = response.json()
    assert [r["conversation_id"] for r in body] == ["conv-b", "conv-a"]
```

- [ ] **Step 2: Rodar e confirmar a falha**

Run: `cd backend && .venv/bin/pytest tests/test_tom_escalonamentos_api.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.api.tom_escalonamentos'`

- [ ] **Step 3: Criar o schema de resposta**

Criar `backend/src/app/models/tom_escalonamentos.py`:

```python
"""Schema Pydantic do endpoint de listagem do Monitor de Tom (R8, Fase 4B)
— ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §6.2.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EscalonamentoResponse(BaseModel):
    id: UUID
    conversation_id: str
    mensagem: str
    motivo: str | None
    confianca: float
    provider_efetivo: str
    criado_em: datetime
```

- [ ] **Step 4: Criar o endpoint**

Criar `backend/src/app/api/tom_escalonamentos.py`:

```python
"""Endpoint administrativo de listagem dos casos escalonados pelo Monitor
de Tom (R8, Fase 4B) — ver
docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §6.2. Sem UI
dedicada nesta entrega, só a API, para inspeção manual/demonstração.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.models import TomEscalonamento
from app.models.tom_escalonamentos import EscalonamentoResponse
from app.router.tone_monitor import listar_escalonamentos

router = APIRouter(prefix="/api/admin/tom", tags=["tom-escalonamentos"])


def _to_response(registro: TomEscalonamento) -> EscalonamentoResponse:
    return EscalonamentoResponse(
        id=registro.id,
        conversation_id=registro.conversation_id,
        mensagem=registro.mensagem,
        motivo=registro.motivo,
        confianca=registro.confianca,
        provider_efetivo=registro.provider_efetivo,
        criado_em=registro.criado_em,
    )


@router.get("/escalonamentos", response_model=list[EscalonamentoResponse])
async def get_escalonamentos(
    session: AsyncSession = Depends(get_db_session),
) -> list[EscalonamentoResponse]:
    # MVP: LIMIT 100 fixo, sem paginação — mesma simplicidade de outras
    # listagens administrativas do projeto.
    registros = await listar_escalonamentos(session)
    return [_to_response(registro) for registro in registros]
```

- [ ] **Step 5: Registrar o router em `main.py`**

Em `backend/src/app/main.py`, adicionar o import junto dos demais routers (ordem alfabética, depois de `app.api.runtime_settings`):

```python
from app.api.tom_escalonamentos import router as tom_escalonamentos_router
```

E, junto dos demais `app.include_router(...)` ao final de `create_app`, adicionar:

```python
    app.include_router(tom_escalonamentos_router)
```

- [ ] **Step 6: Rodar e confirmar que passa**

Run: `cd backend && .venv/bin/pytest tests/test_tom_escalonamentos_api.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 7: Commitar**

```bash
git add backend/src/app/models/tom_escalonamentos.py backend/src/app/api/tom_escalonamentos.py \
  backend/src/app/main.py backend/tests/test_tom_escalonamentos_api.py
git commit -m "feat(tom): adiciona GET /api/admin/tom/escalonamentos (R8)"
```

---

### Task 9: Verificação E2E, ROADMAP.md e ARCHITECTURE.md

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `docs/ARCHITECTURE.md`

**Interfaces:** Nenhuma nova — task de verificação e fechamento de documentação.

- [ ] **Step 1: Rodar a suíte completa do backend**

Run: `cd backend && .venv/bin/pytest -v`
Expected: PASS (nenhum teste pré-existente quebrado pelas Tasks 1-8)

- [ ] **Step 2: Rodar `ruff` (lint) sobre os arquivos tocados**

Run: `cd backend && .venv/bin/ruff check src/app/config.py src/app/models/runtime_settings.py src/app/api/runtime_settings.py src/app/main.py src/app/db/models.py src/app/router/openrouter_client.py src/app/router/tone_monitor.py src/app/router/orchestrator.py src/app/api/chat.py src/app/models/tom_escalonamentos.py src/app/api/tom_escalonamentos.py`
Expected: sem erros. Corrigir qualquer achado antes de prosseguir.

- [ ] **Step 3: Subir a infraestrutura local e aplicar a migração contra o Postgres real**

Run: `cd backend && docker compose up -d postgres && .venv/bin/alembic upgrade head`
Expected: migração `0006` aplicada sem erro. Se `docker compose` não estiver disponível neste ambiente, reportar isso explicitamente em vez de simular — não é bloqueante para o restante da verificação (SQLite já cobriu a lógica de CRUD nas Tasks 2/5/8).

- [ ] **Step 4: Subir o backend e verificar o fluxo real via chat**

Run: `cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000` (background)

Com o backend no ar (e Ollama respondendo em `local_model_base_url`), enviar uma mensagem com sinal forte de insatisfação:

```bash
curl -N -X POST http://localhost:8000/api/chat/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Isso é um absurdo, nunca mais compro nessa loja!"}'
```

(`-N` desliga o buffer do curl para exibir o stream SSE bruto conforme chega.) Confirmar visualmente:
- o evento `escalonamento` aparece antes do `done`, com `motivo` e `confianca`;
- a resposta normal do domínio (`token`s + `done`) continua sendo gerada normalmente, sem ser interrompida;
- `curl http://localhost:8000/api/admin/tom/escalonamentos` retorna o caso recém-criado (`motivo`, `confianca`, `provider_efetivo` preenchidos).

Isso confirma que a dependência `Depends(get_db_session)` permanece aberta durante toda a duração do `StreamingResponse` (comportamento do FastAPI/Starlette instalados neste projeto, versões atuais — ver Task 7) e que a persistência realmente acontece em produção, não só nos testes com SQLite em memória.

- [ ] **Step 5: Marcar os dois itens do roadmap como concluídos**

Em `docs/ROADMAP.md`, alterar as linhas 258-261 de:

```
- [ ] Implementar classificador leve de sentimento/urgência (heurística +
      LLM leve)
- [ ] Implementar alerta e transferência simulada para atendente humano + log
      dos casos escalonados
```

para:

```
- [x] Implementar classificador leve de sentimento/urgência (heurística +
      LLM leve)
- [x] Implementar alerta e transferência simulada para atendente humano + log
      dos casos escalonados (evento SSE `escalonamento` + tabela
      `tom_escalonamentos` — o banner visual no frontend fica para a Fase 8,
      ver `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md` §9)
```

E atualizar a nota de contexto logo acima (linha 246), de:

```
> R8 (monitor de tom) é a Fase 4B, com spec própria ainda a escrever.
```

para:

```
> R8 (monitor de tom) implementado como Fase 4B (backend) — ver
> `docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md`. Banner
> visual no frontend consumindo o evento `escalonamento` fica para a
> Fase 8 (item próprio do roadmap).
```

- [ ] **Step 6: Registrar a decisão em `docs/ARCHITECTURE.md` §5**

Em `docs/ARCHITECTURE.md`, logo antes de `### Tabela de escopo por requisito` (depois do parágrafo "Correção (achado importante 1 da revisão final do branch, 2026-09-23)..."), adicionar:

```markdown
**Monitor de Tom (R8, Fase 4B, decisão registrada em 2026-09-23):**
implementado como checagem transversal (`app.router.tone_monitor.analyze_tone`)
que roda no início de `handle_message`, antes da classificação de domínio,
sem substituir a resposta normal — ver
`docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md`. Mesmo padrão
de dois provedores configuráveis do classificador de intenção
(`TONE_MONITOR_PROVIDER`: `heuristica_llm` — heurística de palavras-chave +
sinais estruturais, com fallback ao LLM local, — ou `jev_openrouter`, com
degradação automática para `heuristica_llm` em qualquer falha do Jev, mesma
lógica de `ClassificationResult.provider_efetivo`). Primeira escalada de
cada conversa emite o evento SSE `escalonamento` (`docs/FRONTEND.md` §4),
persiste um registro em `tom_escalonamentos` (Postgres, migração `0006`) e
loga o evento estruturado `tom_escalonado`. `# MVP: sem mecanismo de
"des-escalar" uma conversa já marcada (estado em memória por processo, mesma
limitação já aceita para o fluxo de agendamento); sem fila real de
atendimento humano nem painel administrativo visual — só a API de listagem
(`GET /api/admin/tom/escalonamentos`) e o log estruturado, para inspeção
manual/demonstração`. Banner visual no frontend consumindo o evento
`escalonamento` é a Fase 8 (fora de escopo desta entrega).
```

- [ ] **Step 7: Commitar**

```bash
git add docs/ROADMAP.md docs/ARCHITECTURE.md
git commit -m "docs(tom): fecha R8 no roadmap e registra decisão em ARCHITECTURE.md"
```
