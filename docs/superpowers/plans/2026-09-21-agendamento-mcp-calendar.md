# Agendamento via MCP Calendar (R11, Fase 4A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Nota (2026-09-23):** o "MCP oficial do Google Calendar" descrito neste
> plano (`calendarmcp.googleapis.com`, autenticação via
> `scripts/authorize_google_calendar.py` guardando client_id/secret/refresh
> token no backend) foi trocado — esse serviço está em Developer Preview e
> não aceita contas Gmail pessoais. O sistema hoje consome um MCP de
> terceiro self-hosted (`calendar-mcp-server`), que gerencia sua própria
> autenticação; `scripts/authorize_google_calendar.py` e
> `_load_client_secrets`/`_load_refresh_token`/`_get_access_token` em
> `google_calendar.py` foram removidos. Ver decisão completa e atual em
> `docs/ARCHITECTURE.md` §5 ("Decisão revista (Fase 4A, troca do MCP
> consumido, 2026-09-23)"). Este documento fica como registro histórico do
> plano original — as tarefas/código abaixo não refletem o estado atual do
> cliente MCP do Calendar.

**Goal:** Fechar R11 — o assistente reconhece a intenção de agendamento de visita, coleta data/hora/nome/e-mail/telefone ao longo da conversa, valida o horário (expediente + conflito de agenda) e, com confirmação explícita do visitante, cria o evento na agenda da empresa via o MCP oficial do Google Calendar, que dispara a confirmação por e-mail sozinho.

**Architecture:** Três módulos novos — `app/router/scheduling.py` (máquina de estado pura: slots, extração via LLM, validação de horário, mensagens), `app/mcp_client/google_calendar.py` (cliente MCP Streamable HTTP com OAuth de refresh token) e `scripts/authorize_google_calendar.py` (consentimento único do admin) — mais um novo ramo em `orchestrator.handle_message` para `domain == "agendamento"` que substitui o stub atual.

**Tech Stack:** Python 3.13, FastAPI, `mcp>=1.0` (SDK oficial, transporte Streamable HTTP via `mcp.client.streamable_http`), `httpx` (chamadas REST simples: refresh de token OAuth, e é o que o resto do backend já usa), `pydantic`/`pydantic-settings`, `pytest` + `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md` — este plano segue a spec seção a seção; os executores devem ler as duas.

## Global Constraints

- Endpoint MCP: `https://calendarmcp.googleapis.com/mcp/v1`, transporte Streamable HTTP (spec §2).
- Token endpoint OAuth: `https://oauth2.googleapis.com/token`, `grant_type=refresh_token` (spec §3).
- Campos obrigatórios antes de criar o evento: `data_hora`, `nome`, `email`, `telefone` (spec §4).
- Duração fixa da visita: 30 minutos (`fim = data_hora + timedelta(minutes=30)`), calculada em `scheduling.py`, nunca dentro do cliente MCP (spec §5).
- Confirmação explícita do visitante é sempre exigida antes de chamar `create_event` (spec §4.1 passo 5-6).
- Validação de horário (spec §4.3) roda ANTES da etapa de confirmação: expediente local (sem MCP) e depois conflito de agenda via `is_time_available` (MCP `list_events`). Só a agenda configurada em `GOOGLE_CALENDAR_CALENDAR_ID` — nunca múltiplas agendas.
- Confirmação por e-mail é feita pelo próprio Google Calendar (convidado + notificação no `create_event`) — nenhuma infraestrutura de e-mail própria (spec §5, §9).
- Qualquer falha de conexão/autenticação do MCP vira mensagem clara ao visitante + log estruturado `google_calendar_indisponivel`, nunca uma exceção crua (spec §6).
- Nenhuma credencial real em código/commit — só caminhos de arquivo via `.env`/`Settings` (spec §8, `docs/CONVENTIONS.md`).
- Testes sem rede real e sem credenciais reais (spec §7) — todo acesso a LLM/MCP/HTTP é mockado/injetado, mesmo padrão já usado em `tests/test_openrouter_client.py` e `tests/test_orchestrator.py`.

---

## File Structure

**Criar:**
- `backend/src/app/router/scheduling.py` — `BookingSlots`, `SchedulingConfig`, extração de slots via LLM, validação de horário, mensagens ao visitante, estado em memória por `conversation_id`.
- `backend/src/app/mcp_client/google_calendar.py` — `GoogleCalendarMCPClient`, `CalendarClient` (Protocol), `GoogleCalendarAuthError`, `GoogleCalendarConnectionError`.
- `backend/scripts/authorize_google_calendar.py` — script administrativo de consentimento único.
- `backend/tests/test_scheduling.py`
- `backend/tests/test_google_calendar_client.py`
- `backend/tests/test_authorize_google_calendar.py`

**Modificar:**
- `backend/src/app/config.py` — novas settings (token path, expediente).
- `backend/.env.example` — novas variáveis (espelhando `config.py`).
- `backend/src/app/router/orchestrator.py` — novo ramo `_handle_agendamento`, `CalendarClient`/`SchedulingConfig` como parâmetros de `handle_message`, comentário de `RouterDecision.motivo_escalonamento` atualizado.
- `backend/src/app/router/playbooks.py` — remove `_AGENDAMENTO_PLAYBOOK` (morto: o novo fluxo não passa mais por `build_system_prompt`).
- `backend/tests/test_playbooks.py` — remove "agendamento" da lista de domínios com playbook.
- `backend/tests/test_orchestrator.py` — substitui `test_agendamento_sempre_local` (comportamento antigo) por testes do novo fluxo; ajusta `test_ttft_usa_prompt_eval_duration_nao_load_duration` (usava "agendamento" só como atalho para forçar backend local sem RAG).
- `backend/src/app/main.py` — instancia `GoogleCalendarMCPClient`/`SchedulingConfig` em `app.state`.
- `backend/src/app/api/chat.py` — novas dependências (`get_calendar_client`, `get_scheduling_config`), passa `conversation_id`/`calendar_client`/`scheduling_config` para `handle_message`.
- `backend/tests/test_main_app.py` — assere que `app.state.calendar_client`/`app.state.scheduling_config` existem.
- `docs/ROADMAP.md` — marca os itens de R11 na Fase 4 como concluídos.

---

## Task 1: `scheduling.py` — `BookingSlots` e estado em memória por conversa

**Files:**
- Create: `backend/src/app/router/scheduling.py`
- Test: `backend/tests/test_scheduling.py`

**Interfaces:**
- Produces: `BookingSlots` (pydantic `BaseModel`, campos `data_hora: datetime | None`, `nome: str | None`, `email: str | None`, `telefone: str | None`, `awaiting_confirmation: bool = False`; métodos `is_complete() -> bool`, `missing_fields() -> list[str]`); `get_booking_slots(conversation_id: str) -> BookingSlots`; `set_booking_slots(conversation_id: str, slots: BookingSlots) -> None`; `clear_booking_slots(conversation_id: str) -> None`; `reset_all_booking_slots() -> None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_scheduling.py
from datetime import datetime

from app.router.scheduling import (
    BookingSlots,
    clear_booking_slots,
    get_booking_slots,
    reset_all_booking_slots,
    set_booking_slots,
)


def setup_function():
    reset_all_booking_slots()


def test_booking_slots_incompletos_por_padrao():
    slots = BookingSlots()
    assert not slots.is_complete()
    assert set(slots.missing_fields()) == {"data_hora", "nome", "email", "telefone"}


def test_booking_slots_completos_quando_todos_os_campos_preenchidos():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 25, 15, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    assert slots.is_complete()
    assert slots.missing_fields() == []


def test_get_booking_slots_devolve_vazio_para_conversa_desconhecida():
    slots = get_booking_slots("conversa-inexistente")
    assert slots == BookingSlots()


def test_set_e_get_booking_slots_por_conversation_id():
    slots = BookingSlots(nome="Maria")
    set_booking_slots("conversa-1", slots)

    assert get_booking_slots("conversa-1") == slots
    assert get_booking_slots("conversa-2") == BookingSlots()


def test_clear_booking_slots_remove_apenas_a_conversa_informada():
    set_booking_slots("conversa-1", BookingSlots(nome="Maria"))
    set_booking_slots("conversa-2", BookingSlots(nome="João"))

    clear_booking_slots("conversa-1")

    assert get_booking_slots("conversa-1") == BookingSlots()
    assert get_booking_slots("conversa-2") == BookingSlots(nome="João")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.router.scheduling'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/router/scheduling.py
"""Máquina de estado do agendamento de visita (R11, Fase 4A).

Lógica de domínio pura (sem I/O de LLM/MCP, sem tipos de streaming SSE) —
consumida por `app.router.orchestrator`, que faz a ponte com o protocolo de
streaming e chama o MCP de verdade. Ver
docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md.

# MVP: estado de agendamento guardado em memória por `conversation_id`
(dict de processo), mesmo padrão MVP de `_conversation_history` em
`app.api.chat` — perdido em restart do processo, sem persistência em banco
(a persistência de conversa é Fase 6, ainda não implementada).
"""

from datetime import datetime

from pydantic import BaseModel

_CAMPOS_OBRIGATORIOS = ("data_hora", "nome", "email", "telefone")


class BookingSlots(BaseModel):
    data_hora: datetime | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    awaiting_confirmation: bool = False

    def is_complete(self) -> bool:
        return all(getattr(self, campo) is not None for campo in _CAMPOS_OBRIGATORIOS)

    def missing_fields(self) -> list[str]:
        return [campo for campo in _CAMPOS_OBRIGATORIOS if getattr(self, campo) is None]


_booking_slots: dict[str, BookingSlots] = {}


def get_booking_slots(conversation_id: str) -> BookingSlots:
    return _booking_slots.get(conversation_id, BookingSlots())


def set_booking_slots(conversation_id: str, slots: BookingSlots) -> None:
    _booking_slots[conversation_id] = slots


def clear_booking_slots(conversation_id: str) -> None:
    _booking_slots.pop(conversation_id, None)


def reset_all_booking_slots() -> None:
    """Limpa o estado em memória — usado pelos testes para isolar casos."""
    _booking_slots.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v`
Expected: PASS (5 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/scheduling.py backend/tests/test_scheduling.py
git commit -m "feat(agendamento): estado de coleta de dados em memória por conversa (R11, Fase 4A)"
```

---

## Task 2: `scheduling.py` — Extração de slots via LLM

**Files:**
- Modify: `backend/src/app/router/scheduling.py`
- Test: `backend/tests/test_scheduling.py`

**Interfaces:**
- Consumes: `app.router.llm_client.LLMClient.generate(prompt: str) -> LLMResponse` (já existe); `BookingSlots` (Task 1).
- Produces: `SlotExtractionResult` (pydantic, mesmos 4 campos de `BookingSlots` + `confirmacao: bool | None`); `async def extract_booking_slots(message: str, recent_messages: list[str], current_slots: BookingSlots, llm_client: LLMClient) -> SlotExtractionResult`; `def merge_slots(current: BookingSlots, extraction: SlotExtractionResult) -> BookingSlots`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_scheduling.py (adicionar ao final do arquivo)
import pytest

from app.router.llm_client import LLMResponse
from app.router.scheduling import (
    SlotExtractionResult,
    extract_booking_slots,
    merge_slots,
)


class _FakeLLMClient:
    def __init__(self, text: str) -> None:
        self._text = text
        self.last_prompt: str | None = None

    async def generate(self, prompt: str) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(text=self._text, total_duration_ms=10.0)

    async def is_model_ready(self) -> bool:
        return True

    def generate_stream(self, prompt: str):
        raise NotImplementedError


async def test_extract_booking_slots_parseia_json_da_resposta():
    llm = _FakeLLMClient(
        '{"data_hora": "2026-09-25T15:00:00-03:00", "nome": "Maria", '
        '"email": null, "telefone": null, "confirmacao": null}'
    )

    resultado = await extract_booking_slots(
        message="quero marcar dia 25 de setembro às 15h, meu nome é Maria",
        recent_messages=[],
        current_slots=BookingSlots(),
        llm_client=llm,
    )

    assert resultado.nome == "Maria"
    assert resultado.email is None
    assert resultado.confirmacao is None
    assert "quero marcar dia 25" in llm.last_prompt


async def test_extract_booking_slots_aceita_json_em_bloco_de_codigo():
    llm = _FakeLLMClient(
        '```json\n{"data_hora": null, "nome": null, "email": "a@b.com", '
        '"telefone": null, "confirmacao": true}\n```'
    )

    resultado = await extract_booking_slots(
        message="pode confirmar, meu email é a@b.com",
        recent_messages=[],
        current_slots=BookingSlots(nome="Maria", awaiting_confirmation=True),
        llm_client=llm,
    )

    assert resultado.email == "a@b.com"
    assert resultado.confirmacao is True


async def test_extract_booking_slots_resposta_invalida_nao_quebra_o_turno():
    llm = _FakeLLMClient("não sei responder isso")

    resultado = await extract_booking_slots(
        message="oi",
        recent_messages=[],
        current_slots=BookingSlots(),
        llm_client=llm,
    )

    assert resultado == SlotExtractionResult()


def test_merge_slots_preserva_campos_ja_coletados():
    atual = BookingSlots(nome="Maria", email="maria@example.com")
    extraido = SlotExtractionResult(telefone="11999999999")

    resultado = merge_slots(atual, extraido)

    assert resultado.nome == "Maria"
    assert resultado.email == "maria@example.com"
    assert resultado.telefone == "11999999999"


def test_merge_slots_sobrescreve_quando_novo_valor_vem_preenchido():
    atual = BookingSlots(nome="Maria")
    extraido = SlotExtractionResult(nome="Maria Silva")

    resultado = merge_slots(atual, extraido)

    assert resultado.nome == "Maria Silva"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v -k extract_booking_slots or merge_slots`
Expected: FAIL com `ImportError`/`AttributeError` (símbolos ainda não existem)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/router/scheduling.py (adicionar)
import json
import re

from pydantic import ValidationError

from app.router.llm_client import LLMClient

# MVP: mesmo tratamento de `app.router.classifier._strip_code_fence` — alguns
# modelos locais envolvem o JSON pedido em um bloco de código markdown mesmo
# instruídos a responder só com JSON.
_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


class SlotExtractionResult(BaseModel):
    data_hora: datetime | None = None
    nome: str | None = None
    email: str | None = None
    telefone: str | None = None
    confirmacao: bool | None = None


_EXTRACTION_PROMPT_TEMPLATE = """\
Você está ajudando a coletar dados para agendar uma visita comercial. \
Extraia da mensagem do cliente os campos que ele informou NESTA mensagem, \
sem inventar nada e sem repetir dados que não foram ditos agora. Datas/horas \
devem vir em ISO 8601 com fuso (ex.: "2026-09-25T15:00:00-03:00").

Dados já coletados até agora: {slots_conhecidos}
O sistema está aguardando uma confirmação do cliente? {aguardando_confirmacao}

Contexto recente da conversa:
{contexto}

Mensagem atual do cliente: {mensagem}

Responda APENAS com JSON no formato: {{"data_hora": "...", "nome": "...", \
"email": "...", "telefone": "...", "confirmacao": true}} — use null para \
qualquer campo não informado NESTA mensagem. "confirmacao" só deve ser true \
se o cliente estiver claramente confirmando (ex.: "sim", "pode confirmar", \
"isso mesmo") E o sistema estiver aguardando confirmação; caso contrário, \
null."""


def _parse_extraction(raw_text: str) -> SlotExtractionResult:
    parsed = json.loads(_strip_code_fence(raw_text))
    return SlotExtractionResult(**parsed)


async def extract_booking_slots(
    message: str,
    recent_messages: list[str],
    current_slots: BookingSlots,
    llm_client: LLMClient,
) -> SlotExtractionResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
        slots_conhecidos=current_slots.model_dump_json(exclude={"awaiting_confirmation"}),
        aguardando_confirmacao="sim" if current_slots.awaiting_confirmation else "não",
        contexto=contexto,
        mensagem=message,
    )
    response = await llm_client.generate(prompt)
    try:
        return _parse_extraction(response.text)
    except (json.JSONDecodeError, ValidationError, TypeError):
        # MVP: resposta do LLM não é JSON de extração válido — não quebra o
        # turno, trata como "nada extraído nesta mensagem" (mesmo espírito de
        # `app.router.classifier._classify_with_llm`, que cai para a
        # heurística no caso análogo; aqui não há heurística de agendamento
        # por regex, só o loop de pedir de novo no orchestrator).
        return SlotExtractionResult()


def merge_slots(current: BookingSlots, extraction: SlotExtractionResult) -> BookingSlots:
    campos_extraidos = {
        "data_hora": extraction.data_hora,
        "nome": extraction.nome,
        "email": extraction.email,
        "telefone": extraction.telefone,
    }
    atualizacoes = {campo: valor for campo, valor in campos_extraidos.items() if valor is not None}
    return current.model_copy(update=atualizacoes)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v`
Expected: PASS (todos os testes do arquivo, incluindo os do Task 1)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/scheduling.py backend/tests/test_scheduling.py
git commit -m "feat(agendamento): extração de slots de agendamento via LLM (R11, Fase 4A)"
```

---

## Task 3: `scheduling.py` — Validação de horário e mensagens ao visitante

**Files:**
- Modify: `backend/src/app/router/scheduling.py`
- Test: `backend/tests/test_scheduling.py`

**Interfaces:**
- Produces: `SchedulingConfig` (pydantic: `timezone: str`, `expediente_dias: str`, `expediente_inicio: str`, `expediente_fim: str`); `HorarioInvalidoError(Exception)` (atributo `.motivo: str`); `def validar_expediente(data_hora: datetime, config: SchedulingConfig) -> None` (levanta `HorarioInvalidoError` ou não faz nada); `DURACAO_VISITA: timedelta` (30 min); `def mensagem_campos_faltando(slots: BookingSlots) -> str`; `def mensagem_pedir_confirmacao(slots: BookingSlots, timezone: str) -> str`; `def mensagem_sucesso(slots: BookingSlots, timezone: str) -> str`; `MSG_ERRO_MCP: str`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_scheduling.py (adicionar ao final do arquivo)
from datetime import timedelta

from app.router.scheduling import (
    DURACAO_VISITA,
    MSG_ERRO_MCP,
    HorarioInvalidoError,
    SchedulingConfig,
    mensagem_campos_faltando,
    mensagem_pedir_confirmacao,
    mensagem_sucesso,
    validar_expediente,
)

_CONFIG = SchedulingConfig(
    timezone="America/Sao_Paulo",
    expediente_dias="seg-sex",
    expediente_inicio="09:00",
    expediente_fim="18:00",
)


def test_duracao_visita_e_30_minutos():
    assert DURACAO_VISITA == timedelta(minutes=30)


def test_validar_expediente_aceita_horario_valido():
    # 2026-09-24 é uma quinta-feira, 10h — dentro do expediente seg-sex 9-18h.
    validar_expediente(datetime(2026, 9, 24, 10, 0), _CONFIG)  # não levanta


def test_validar_expediente_rejeita_data_no_passado():
    with pytest.raises(HorarioInvalidoError):
        validar_expediente(datetime(2020, 1, 1, 10, 0), _CONFIG)


def test_validar_expediente_rejeita_fim_de_semana():
    # 2026-09-26 é sábado.
    with pytest.raises(HorarioInvalidoError) as exc_info:
        validar_expediente(datetime(2026, 9, 26, 10, 0), _CONFIG)
    assert "expediente" in exc_info.value.motivo.lower()


def test_validar_expediente_rejeita_fora_do_horario():
    # 2026-09-24 é quinta, 20h — fora do expediente até 18h.
    with pytest.raises(HorarioInvalidoError):
        validar_expediente(datetime(2026, 9, 24, 20, 0), _CONFIG)


def test_mensagem_campos_faltando_lista_um_campo():
    slots = BookingSlots(data_hora=datetime(2026, 9, 24, 10, 0), nome="Maria", email="m@x.com")
    texto = mensagem_campos_faltando(slots)
    assert "telefone" in texto.lower()


def test_mensagem_campos_faltando_lista_varios_campos():
    slots = BookingSlots()
    texto = mensagem_campos_faltando(slots)
    assert "nome" in texto.lower()
    assert "e-mail" in texto.lower()
    assert "telefone" in texto.lower()


def test_mensagem_pedir_confirmacao_inclui_dados_coletados():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 24, 10, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    texto = mensagem_pedir_confirmacao(slots, "America/Sao_Paulo")
    assert "Maria" in texto
    assert "maria@example.com" in texto
    assert "confirmar" in texto.lower()


def test_mensagem_sucesso_menciona_email():
    slots = BookingSlots(
        data_hora=datetime(2026, 9, 24, 10, 0),
        nome="Maria",
        email="maria@example.com",
        telefone="11999999999",
    )
    texto = mensagem_sucesso(slots, "America/Sao_Paulo")
    assert "maria@example.com" in texto


def test_msg_erro_mcp_nao_promete_confirmacao_automatica():
    assert "não consegui confirmar" in MSG_ERRO_MCP.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v`
Expected: FAIL com `ImportError` (símbolos novos ainda não existem)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/router/scheduling.py (adicionar)
from datetime import time as dt_time
from datetime import timedelta
from zoneinfo import ZoneInfo

DURACAO_VISITA = timedelta(minutes=30)

_DIAS_SEMANA = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}


class SchedulingConfig(BaseModel):
    timezone: str
    expediente_dias: str
    expediente_inicio: str
    expediente_fim: str


class HorarioInvalidoError(Exception):
    def __init__(self, motivo: str) -> None:
        self.motivo = motivo
        super().__init__(motivo)


def _parse_dias_expediente(dias_str: str) -> set[int]:
    # MVP: só o formato "seg-sex" (intervalo contíguo) ou "seg,qua,sex"
    # (lista) — sem combinações mais ricas (ex. "seg-qua,sex").
    dias_str = dias_str.strip().lower()
    if "-" in dias_str:
        inicio_str, fim_str = dias_str.split("-", 1)
        inicio, fim = _DIAS_SEMANA[inicio_str.strip()], _DIAS_SEMANA[fim_str.strip()]
        if inicio <= fim:
            return set(range(inicio, fim + 1))
        return set(range(inicio, 7)) | set(range(0, fim + 1))
    return {_DIAS_SEMANA[dia.strip()] for dia in dias_str.split(",")}


def validar_expediente(data_hora: datetime, config: SchedulingConfig) -> None:
    tz = ZoneInfo(config.timezone)
    agora = datetime.now(tz)
    dh = data_hora if data_hora.tzinfo else data_hora.replace(tzinfo=tz)
    dh = dh.astimezone(tz)

    if dh <= agora:
        raise HorarioInvalidoError(
            "Esse horário já passou. Pode sugerir uma data e hora futuras?"
        )

    dias_validos = _parse_dias_expediente(config.expediente_dias)
    if dh.weekday() not in dias_validos:
        raise HorarioInvalidoError(
            f"Só agendamos visitas em dias úteis ({config.expediente_dias}). "
            "Pode escolher outro dia?"
        )

    hora_inicio = dt_time.fromisoformat(config.expediente_inicio)
    hora_fim = dt_time.fromisoformat(config.expediente_fim)
    if not (hora_inicio <= dh.time() < hora_fim):
        raise HorarioInvalidoError(
            f"Nosso expediente para visitas é das {config.expediente_inicio} às "
            f"{config.expediente_fim}. Pode escolher outro horário nessa faixa?"
        )


_ROTULOS_CAMPOS = {
    "data_hora": "a data e o horário desejados para a visita",
    "nome": "seu nome",
    "email": "seu e-mail",
    "telefone": "seu telefone",
}


def mensagem_campos_faltando(slots: BookingSlots) -> str:
    faltando = [_ROTULOS_CAMPOS[campo] for campo in slots.missing_fields()]
    if len(faltando) == 1:
        pedido = faltando[0]
    else:
        pedido = ", ".join(faltando[:-1]) + " e " + faltando[-1]
    return f"Para agendar sua visita, ainda preciso de: {pedido}."


def _formatar_data_hora(data_hora: datetime, timezone: str) -> str:
    tz = ZoneInfo(timezone)
    dh = data_hora if data_hora.tzinfo else data_hora.replace(tzinfo=tz)
    return dh.astimezone(tz).strftime("%d/%m/%Y às %H:%M")


def mensagem_pedir_confirmacao(slots: BookingSlots, timezone: str) -> str:
    data_formatada = _formatar_data_hora(slots.data_hora, timezone)
    return (
        f"Só confirmando antes de agendar: visita em {data_formatada}, em nome "
        f"de {slots.nome}, e-mail {slots.email}, telefone {slots.telefone}. "
        "Posso confirmar?"
    )


def mensagem_sucesso(slots: BookingSlots, timezone: str) -> str:
    data_formatada = _formatar_data_hora(slots.data_hora, timezone)
    return (
        f"Prontinho! Sua visita foi agendada para {data_formatada}. Você vai "
        f"receber a confirmação por e-mail em {slots.email}."
    )


MSG_ERRO_MCP = (
    "No momento não consegui confirmar o agendamento automaticamente. Um "
    "atendente da nossa equipe vai entrar em contato para confirmar os "
    "detalhes. Pedimos desculpas pelo transtorno."
)
```

`test_validar_expediente_aceita_horario_valido`/`test_validar_expediente_rejeita_data_no_passado` usam datas fixas de 2026 — como "hoje" nos testes é depois de 2026-09-21 (ver contexto da sessão), ajuste a data de "horário válido" para pelo menos alguns dias à frente da data real de execução dos testes se necessário (o teste de "no passado" usa 2020, sempre seguro).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_scheduling.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/scheduling.py backend/tests/test_scheduling.py
git commit -m "feat(agendamento): validação de expediente e mensagens ao visitante (R11, Fase 4A)"
```

---

## Task 4: `google_calendar.py` — Exceções, Protocol e leitura de credenciais

**Files:**
- Create: `backend/src/app/mcp_client/google_calendar.py`
- Test: `backend/tests/test_google_calendar_client.py`

**Interfaces:**
- Produces: `GoogleCalendarAuthError(Exception)`; `GoogleCalendarConnectionError(Exception)`; `CalendarClient` (`Protocol` com `is_time_available`/`create_event`, assinaturas do Task 6); função interna `_load_client_secrets(path: str) -> tuple[str, str]`; função interna `_load_refresh_token(path: str) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_google_calendar_client.py
import json

import pytest

from app.mcp_client.google_calendar import (
    GoogleCalendarAuthError,
    _load_client_secrets,
    _load_refresh_token,
)


def test_load_client_secrets_le_bloco_installed(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"installed": {"client_id": "abc", "client_secret": "xyz"}}))

    client_id, client_secret = _load_client_secrets(str(path))

    assert client_id == "abc"
    assert client_secret == "xyz"


def test_load_client_secrets_le_bloco_web(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"web": {"client_id": "abc", "client_secret": "xyz"}}))

    client_id, client_secret = _load_client_secrets(str(path))

    assert client_id == "abc"
    assert client_secret == "xyz"


def test_load_client_secrets_arquivo_inexistente_vira_auth_error():
    with pytest.raises(GoogleCalendarAuthError):
        _load_client_secrets("/caminho/que/nao/existe.json")


def test_load_client_secrets_formato_invalido_vira_auth_error(tmp_path):
    path = tmp_path / "credentials.json"
    path.write_text(json.dumps({"algo_errado": {}}))

    with pytest.raises(GoogleCalendarAuthError):
        _load_client_secrets(str(path))


def test_load_refresh_token_le_do_arquivo(tmp_path):
    path = tmp_path / "token.json"
    path.write_text(json.dumps({"refresh_token": "meu-refresh-token"}))

    assert _load_refresh_token(str(path)) == "meu-refresh-token"


def test_load_refresh_token_arquivo_inexistente_vira_auth_error():
    with pytest.raises(GoogleCalendarAuthError):
        _load_refresh_token("/caminho/que/nao/existe.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.mcp_client.google_calendar'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/mcp_client/google_calendar.py
"""Cliente MCP do Google Calendar (R11, Fase 4A) — consome o servidor MCP
remoto oficial do Google (`calendarmcp.googleapis.com`), não um servidor
próprio (decisão registrada em
docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md §2).

# MVP: autenticação via refresh token de um consentimento único feito pelo
admin (`scripts/authorize_google_calendar.py`), não por visitante — uma só
agenda da empresa (`GOOGLE_CALENDAR_CALENDAR_ID`), sem reautenticação
automática (ver spec §3).
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Protocol


class GoogleCalendarAuthError(Exception):
    """Falha ao carregar credenciais ou renovar o access token."""


class GoogleCalendarConnectionError(Exception):
    """Falha de rede/protocolo ao falar com o MCP do Google Calendar."""


class CalendarClient(Protocol):
    async def is_time_available(self, start: datetime, end: datetime) -> bool: ...

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> str: ...


def _load_client_secrets(path: str) -> tuple[str, str]:
    try:
        raw = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise GoogleCalendarAuthError(
            f"Não foi possível ler o arquivo de credenciais do Google Calendar "
            f"({path}): {exc}"
        ) from exc

    bloco = raw.get("installed") or raw.get("web")
    if not bloco or "client_id" not in bloco or "client_secret" not in bloco:
        raise GoogleCalendarAuthError(
            f"Arquivo de credenciais do Google Calendar ({path}) não tem o "
            "formato esperado (client_secrets.json do Google Cloud Console, "
            "com bloco 'installed' ou 'web')."
        )
    return bloco["client_id"], bloco["client_secret"]


def _load_refresh_token(path: str) -> str:
    try:
        raw = json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise GoogleCalendarAuthError(
            f"Não foi possível ler o refresh token do Google Calendar ({path}): "
            f"{exc}. Rode backend/scripts/authorize_google_calendar.py para "
            "gerá-lo."
        ) from exc

    refresh_token = raw.get("refresh_token")
    if not refresh_token:
        raise GoogleCalendarAuthError(f"Arquivo de token ({path}) não contém 'refresh_token'.")
    return refresh_token
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v`
Expected: PASS (6 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/mcp_client/google_calendar.py backend/tests/test_google_calendar_client.py
git commit -m "feat(agendamento): leitura de credenciais/token do Google Calendar (R11, Fase 4A)"
```

---

## Task 5: `google_calendar.py` — Refresh de access token OAuth

**Files:**
- Modify: `backend/src/app/mcp_client/google_calendar.py`
- Test: `backend/tests/test_google_calendar_client.py`

**Interfaces:**
- Consumes: `_load_client_secrets`, `_load_refresh_token` (Task 4).
- Produces: `GoogleCalendarMCPClient.__init__(self, credentials_path: str, token_path: str, calendar_id: str, token_http_client: httpx.AsyncClient | None = None, session_factory: ... | None = None)`; `async def _get_access_token(self) -> str` (método "privado", testado via acesso direto — mesmo padrão de `_classify_with_llm` sendo testado isoladamente no roteador).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_google_calendar_client.py (adicionar ao final do arquivo)
import httpx

from app.mcp_client.google_calendar import GoogleCalendarMCPClient


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


def _client(tmp_path, transport: httpx.MockTransport) -> GoogleCalendarMCPClient:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csecret"}}))
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"refresh_token": "rtoken"}))

    return GoogleCalendarMCPClient(
        credentials_path=str(credentials_path),
        token_path=str(token_path),
        calendar_id="primary",
        token_http_client=httpx.AsyncClient(transport=transport),
    )


async def test_get_access_token_troca_refresh_token_por_access_token(tmp_path):
    client = _client(tmp_path, _mock_transport({"access_token": "novo-token", "expires_in": 3600}))

    token = await client._get_access_token()

    assert token == "novo-token"


async def test_get_access_token_reaproveita_token_em_cache(tmp_path):
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})

    client = _client(tmp_path, httpx.MockTransport(handler))

    primeiro = await client._get_access_token()
    segundo = await client._get_access_token()

    assert primeiro == segundo == "token-1"
    assert len(chamadas) == 1  # segunda chamada não bateu na rede — usou o cache


async def test_get_access_token_renova_quando_expirado(tmp_path):
    respostas = [
        {"access_token": "token-1", "expires_in": -10},  # já "expirado" na criação
        {"access_token": "token-2", "expires_in": 3600},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=respostas.pop(0))

    client = _client(tmp_path, httpx.MockTransport(handler))

    primeiro = await client._get_access_token()
    segundo = await client._get_access_token()

    assert primeiro == "token-1"
    assert segundo == "token-2"


async def test_get_access_token_erro_http_vira_auth_error(tmp_path):
    client = _client(tmp_path, _mock_transport({"error": "invalid_grant"}, status_code=400))

    with pytest.raises(GoogleCalendarAuthError):
        await client._get_access_token()


async def test_get_access_token_resposta_sem_access_token_vira_auth_error(tmp_path):
    client = _client(tmp_path, _mock_transport({"expires_in": 3600}))

    with pytest.raises(GoogleCalendarAuthError):
        await client._get_access_token()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v -k get_access_token`
Expected: FAIL com `ImportError: cannot import name 'GoogleCalendarMCPClient'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/mcp_client/google_calendar.py (adicionar)
import httpx

_TOKEN_URL = "https://oauth2.googleapis.com/token"
# MVP: margem de segurança — renova o access token 60s antes do prazo
# reportado pelo Google, em vez de esperar expirar de verdade.
_MARGEM_RENOVACAO_S = 60


class GoogleCalendarMCPClient:
    def __init__(
        self,
        credentials_path: str,
        token_path: str,
        calendar_id: str,
        token_http_client: httpx.AsyncClient | None = None,
        session_factory=None,
    ) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._calendar_id = calendar_id
        self._token_http_client = token_http_client or httpx.AsyncClient()
        self._session_factory = session_factory or self._default_session_factory

        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._refresh_token: str | None = None
        self._access_token: str | None = None
        self._access_token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        if self._access_token and time.monotonic() < self._access_token_expires_at:
            return self._access_token

        if self._client_id is None:
            self._client_id, self._client_secret = _load_client_secrets(self._credentials_path)
        if self._refresh_token is None:
            self._refresh_token = _load_refresh_token(self._token_path)

        try:
            response = await self._token_http_client.post(
                _TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GoogleCalendarAuthError(f"Falha ao renovar access token: {exc}") from exc

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise GoogleCalendarAuthError("Resposta de refresh de token sem 'access_token'.")

        self._access_token = access_token
        self._access_token_expires_at = (
            time.monotonic() + payload.get("expires_in", 3600) - _MARGEM_RENOVACAO_S
        )
        return access_token

    def _default_session_factory(self, access_token: str):
        raise NotImplementedError  # implementado no Task 6
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/mcp_client/google_calendar.py backend/tests/test_google_calendar_client.py
git commit -m "feat(agendamento): renovação de access token OAuth do Google Calendar (R11, Fase 4A)"
```

---

## Task 6: `google_calendar.py` — `is_time_available` e `create_event` via MCP

**Files:**
- Modify: `backend/src/app/mcp_client/google_calendar.py`
- Test: `backend/tests/test_google_calendar_client.py`

**Interfaces:**
- Consumes: `_get_access_token` (Task 5); SDK `mcp` (`mcp.ClientSession`, `mcp.client.streamable_http.streamable_http_client`, `mcp.shared._httpx_utils.create_mcp_http_client`) para o `_default_session_factory` real.
- Produces: `async def is_time_available(self, start: datetime, end: datetime) -> bool`; `async def create_event(self, summary: str, start: datetime, end: datetime, attendee_email: str, attendee_name: str, description: str = "") -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_google_calendar_client.py (adicionar ao final do arquivo)
from contextlib import asynccontextmanager


class _FakeCallToolResult:
    def __init__(self, structured_content=None, is_error=False, content=None):
        self.structured_content = structured_content
        self.is_error = is_error
        self.content = content or []


class _FakeMCPSession:
    def __init__(self, result=None, exception=None):
        self._result = result
        self._exception = exception
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if self._exception is not None:
            raise self._exception
        return self._result


def _fake_session_factory(session: _FakeMCPSession):
    @asynccontextmanager
    async def factory(access_token: str):
        yield session

    return factory


def _client_com_sessao_fake(tmp_path, session: _FakeMCPSession) -> GoogleCalendarMCPClient:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csecret"}}))
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"refresh_token": "rtoken"}))

    client = GoogleCalendarMCPClient(
        credentials_path=str(credentials_path),
        token_path=str(token_path),
        calendar_id="primary",
        token_http_client=httpx.AsyncClient(
            transport=_mock_transport({"access_token": "tok", "expires_in": 3600})
        ),
        session_factory=_fake_session_factory(session),
    )
    return client


async def test_is_time_available_true_quando_nao_ha_eventos(tmp_path):
    session = _FakeMCPSession(result=_FakeCallToolResult(structured_content={"events": []}))
    client = _client_com_sessao_fake(tmp_path, session)

    disponivel = await client.is_time_available(
        datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30)
    )

    assert disponivel is True
    assert session.calls[0][0] == "list_events"


async def test_is_time_available_false_quando_ha_evento_na_janela(tmp_path):
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"events": [{"id": "evt1"}]})
    )
    client = _client_com_sessao_fake(tmp_path, session)

    disponivel = await client.is_time_available(
        datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30)
    )

    assert disponivel is False


async def test_create_event_retorna_link_do_evento(tmp_path):
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"htmlLink": "https://calendar.google.com/evt1"})
    )
    client = _client_com_sessao_fake(tmp_path, session)

    link = await client.create_event(
        summary="Visita — Maria",
        start=datetime(2026, 9, 24, 10, 0),
        end=datetime(2026, 9, 24, 10, 30),
        attendee_email="maria@example.com",
        attendee_name="Maria",
    )

    assert link == "https://calendar.google.com/evt1"
    nome_tool, argumentos = session.calls[0]
    assert nome_tool == "create_event"
    assert argumentos["attendees"] == [{"email": "maria@example.com", "displayName": "Maria"}]


async def test_call_tool_com_is_error_vira_connection_error(tmp_path):
    session = _FakeMCPSession(result=_FakeCallToolResult(is_error=True, content=["deu erro"]))
    client = _client_com_sessao_fake(tmp_path, session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.is_time_available(datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30))


async def test_call_tool_excecao_de_transporte_vira_connection_error(tmp_path):
    session = _FakeMCPSession(exception=RuntimeError("conexão recusada"))
    client = _client_com_sessao_fake(tmp_path, session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.create_event(
            summary="Visita",
            start=datetime(2026, 9, 24, 10, 0),
            end=datetime(2026, 9, 24, 10, 30),
            attendee_email="a@b.com",
            attendee_name="A",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v -k "is_time_available or create_event or call_tool"`
Expected: FAIL (`AttributeError`/`NotImplementedError` — métodos ainda não implementados de verdade)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/mcp_client/google_calendar.py (adicionar imports no topo)
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

_CALENDAR_MCP_URL = "https://calendarmcp.googleapis.com/mcp/v1"
```

```python
# backend/src/app/mcp_client/google_calendar.py — substituir o
# `_default_session_factory` stub do Task 5 e acrescentar os métodos abaixo
# na classe GoogleCalendarMCPClient

    def _default_session_factory(self, access_token: str):
        @asynccontextmanager
        async def factory():
            headers = {"Authorization": f"Bearer {access_token}"}
            async with create_mcp_http_client(headers=headers) as http_client:
                async with streamable_http_client(
                    _CALENDAR_MCP_URL, http_client=http_client
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        yield session

        return factory()

    async def _call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        access_token = await self._get_access_token()
        try:
            async with self._session_factory(access_token) as session:
                result = await session.call_tool(name, arguments)
        except GoogleCalendarAuthError:
            raise
        except Exception as exc:
            raise GoogleCalendarConnectionError(
                f"Falha ao chamar a tool '{name}' do MCP do Google Calendar: {exc}"
            ) from exc

        if result.is_error:
            raise GoogleCalendarConnectionError(
                f"Tool '{name}' do MCP do Google Calendar retornou erro: {result.content}"
            )
        return result.structured_content or {}

    async def is_time_available(self, start: datetime, end: datetime) -> bool:
        resultado = await self._call_tool(
            "list_events",
            {
                "calendarId": self._calendar_id,
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
            },
        )
        # NOTA: nomes de parâmetros/campos de resposta da tool a confirmar via
        # `tools/list` contra o endpoint real na primeira execução (ver spec
        # §2) — ajustar aqui se o schema real divergir.
        eventos = resultado.get("events", [])
        return len(eventos) == 0

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> str:
        resultado = await self._call_tool(
            "create_event",
            {
                "calendarId": self._calendar_id,
                "summary": summary,
                "description": description,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
                "attendees": [{"email": attendee_email, "displayName": attendee_name}],
                "sendUpdates": "all",
            },
        )
        return resultado.get("htmlLink", "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_google_calendar_client.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/mcp_client/google_calendar.py backend/tests/test_google_calendar_client.py
git commit -m "feat(agendamento): is_time_available/create_event via MCP do Google Calendar (R11, Fase 4A)"
```

---

## Task 7: `scripts/authorize_google_calendar.py` — Consentimento único do admin

**Files:**
- Create: `backend/scripts/authorize_google_calendar.py`
- Test: `backend/tests/test_authorize_google_calendar.py`

**Interfaces:**
- Consumes: `app.config.get_settings` (já existe).
- Produces: `montar_url_autorizacao(client_id: str) -> str`; `trocar_codigo_por_refresh_token(client_id: str, client_secret: str, code: str, http_client: httpx.Client | None = None) -> str`; `main() -> None` (não testado diretamente — é I/O interativo, mesmo critério dos demais scripts de `backend/scripts/`).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_authorize_google_calendar.py
import httpx
import pytest

from scripts.authorize_google_calendar import (
    montar_url_autorizacao,
    trocar_codigo_por_refresh_token,
)


def test_montar_url_autorizacao_inclui_client_id_e_offline():
    url = montar_url_autorizacao("meu-client-id")

    assert "client_id=meu-client-id" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url


def test_trocar_codigo_por_refresh_token_devolve_o_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"refresh_token": "novo-refresh-token"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    token = trocar_codigo_por_refresh_token("cid", "csecret", "codigo-de-autorizacao", client)

    assert token == "novo-refresh-token"


def test_trocar_codigo_por_refresh_token_sem_refresh_token_na_resposta_falha():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "sem-refresh-aqui"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(SystemExit):
        trocar_codigo_por_refresh_token("cid", "csecret", "codigo", client)
```

`backend/tests/__init__.py`/`conftest.py` já configuram o `pythonpath` do projeto — confirme que `backend/scripts/` é importável como pacote (`scripts.authorize_google_calendar`); se `pytest` reclamar de import, adicione `backend/scripts/__init__.py` vazio (verifique primeiro se já existe, os outros scripts de `backend/scripts/` podem já ter resolvido isso).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_authorize_google_calendar.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'scripts.authorize_google_calendar'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/scripts/authorize_google_calendar.py
"""Script administrativo de uso único: gera o refresh token do Google
Calendar (R11, Fase 4A — ver
docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md §3).

Uso:
    cd backend && source .venv/bin/activate
    python scripts/authorize_google_calendar.py

Lê o client secrets JSON (GOOGLE_CALENDAR_CREDENTIALS_PATH), inicia o fluxo
de autorização OAuth 2.0 com access_type=offline, imprime a URL para o admin
abrir no navegador, pede o código de autorização de volta, troca por um
refresh token e salva em GOOGLE_CALENDAR_TOKEN_PATH.

# MVP: fluxo "out-of-band" (copiar/colar o código manualmente) — sem
servidor web local para receber o redirect OAuth, script de linha de comando
mesmo, uso único pelo admin (ver spec §3).
"""

import json
from pathlib import Path
from urllib.parse import urlencode

import httpx

from app.config import get_settings

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/calendar"
_REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"


def montar_url_autorizacao(client_id: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": _REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def trocar_codigo_por_refresh_token(
    client_id: str, client_secret: str, code: str, http_client: httpx.Client | None = None
) -> str:
    client = http_client or httpx.Client()
    response = client.post(
        _TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "redirect_uri": _REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )
    response.raise_for_status()
    payload = response.json()
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        raise SystemExit(
            "A resposta do Google não trouxe refresh_token — revogue o acesso em "
            "https://myaccount.google.com/permissions e rode o script de novo "
            "(o pedido já usa access_type=offline e prompt=consent)."
        )
    return refresh_token


def _carregar_client_secrets(path: str) -> tuple[str, str]:
    raw = json.loads(Path(path).read_text())
    bloco = raw.get("installed") or raw.get("web")
    if not bloco:
        raise SystemExit(f"Arquivo de credenciais ({path}) não tem bloco 'installed'/'web'.")
    return bloco["client_id"], bloco["client_secret"]


def main() -> None:
    settings = get_settings()
    client_id, client_secret = _carregar_client_secrets(settings.google_calendar_credentials_path)

    url = montar_url_autorizacao(client_id)
    print("Abra esta URL no navegador, autorize o acesso à agenda e copie o código:")
    print(url)
    code = input("Cole aqui o código de autorização: ").strip()

    refresh_token = trocar_codigo_por_refresh_token(client_id, client_secret, code)

    token_path = Path(settings.google_calendar_token_path)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(json.dumps({"refresh_token": refresh_token}))
    print(f"Refresh token salvo em {token_path}.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_authorize_google_calendar.py -v`
Expected: PASS (3 testes)

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/authorize_google_calendar.py backend/tests/test_authorize_google_calendar.py
git commit -m "feat(agendamento): script de consentimento único do Google Calendar (R11, Fase 4A)"
```

---

## Task 8: `config.py` e `.env.example` — novas variáveis

**Files:**
- Modify: `backend/src/app/config.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.google_calendar_token_path: str`; `Settings.agendamento_timezone: str`; `Settings.agendamento_expediente_dias: str`; `Settings.agendamento_expediente_inicio: str`; `Settings.agendamento_expediente_fim: str`.

- [ ] **Step 1: Write the failing test**

Leia `backend/tests/test_config.py` primeiro para seguir o padrão exato de asserção já usado lá (provavelmente testa defaults de `Settings()`); adicione, no mesmo estilo:

```python
def test_settings_tem_defaults_de_agendamento():
    settings = Settings()

    assert settings.google_calendar_token_path == "./secrets/google_calendar_token.json"
    assert settings.agendamento_timezone == "America/Sao_Paulo"
    assert settings.agendamento_expediente_dias == "seg-sex"
    assert settings.agendamento_expediente_inicio == "09:00"
    assert settings.agendamento_expediente_fim == "18:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v -k agendamento`
Expected: FAIL com `AttributeError`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/config.py — dentro da classe Settings, logo após a linha
# `google_calendar_calendar_id: str = "primary"`
    # Refresh token gerado por scripts/authorize_google_calendar.py (R11,
    # Fase 4A — ver docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md §3).
    google_calendar_token_path: str = "./secrets/google_calendar_token.json"

    # --- Validação de horário do agendamento (R11, Fase 4A) ---
    agendamento_timezone: str = "America/Sao_Paulo"
    agendamento_expediente_dias: str = "seg-sex"
    agendamento_expediente_inicio: str = "09:00"
    agendamento_expediente_fim: str = "18:00"
```

```bash
# backend/.env.example — logo após a linha GOOGLE_CALENDAR_CALENDAR_ID=primary
```

```
GOOGLE_CALENDAR_TOKEN_PATH=./secrets/google_calendar_token.json

# --- Validação de horário do agendamento (R11) ---
AGENDAMENTO_TIMEZONE=America/Sao_Paulo
AGENDAMENTO_EXPEDIENTE_DIAS=seg-sex
AGENDAMENTO_EXPEDIENTE_INICIO=09:00
AGENDAMENTO_EXPEDIENTE_FIM=18:00
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_config.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/config.py backend/.env.example backend/tests/test_config.py
git commit -m "feat(agendamento): variáveis de configuração de token e expediente (R11, Fase 4A)"
```

---

## Task 9: `orchestrator.py` — Ramo `_handle_agendamento`

**Files:**
- Modify: `backend/src/app/router/orchestrator.py`
- Modify: `backend/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: tudo dos Tasks 1-6 (`BookingSlots`, `SchedulingConfig`, `extract_booking_slots`, `merge_slots`, `validar_expediente`, `HorarioInvalidoError`, `DURACAO_VISITA`, `mensagem_campos_faltando`, `mensagem_pedir_confirmacao`, `mensagem_sucesso`, `MSG_ERRO_MCP`, `get_booking_slots`, `set_booking_slots`, `clear_booking_slots`, `CalendarClient`, `GoogleCalendarAuthError`, `GoogleCalendarConnectionError`).
- Produces: `handle_message(..., conversation_id: str = "", calendar_client: CalendarClient | None = None, scheduling_config: SchedulingConfig | None = None)` — 3 novos parâmetros opcionais (defaults preservam o comportamento dos testes existentes que não exercitam o domínio `agendamento`).

- [ ] **Step 1: Write the failing tests**

Primeiro, REMOVA de `backend/tests/test_orchestrator.py` o teste `test_agendamento_sempre_local` (linhas ~105-126) — seu comportamento (agendamento passa pelo `generate_stream` genérico) deixa de existir. Em seu lugar, adicione:

```python
# backend/tests/test_orchestrator.py (substituir test_agendamento_sempre_local por isto)
from datetime import datetime

from app.mcp_client.google_calendar import (
    CalendarClient,
    GoogleCalendarAuthError,
    GoogleCalendarConnectionError,
)
from app.router.scheduling import (
    BookingSlots,
    SchedulingConfig,
    reset_all_booking_slots,
    set_booking_slots,
)


class _FakeCalendarClient:
    def __init__(
        self,
        available: bool = True,
        create_event_link: str = "https://calendar.google.com/evt1",
        availability_exception: Exception | None = None,
        create_exception: Exception | None = None,
    ) -> None:
        self._available = available
        self._create_event_link = create_event_link
        self._availability_exception = availability_exception
        self._create_exception = create_exception
        self.create_event_calls: list[dict] = []

    async def is_time_available(self, start, end) -> bool:
        if self._availability_exception is not None:
            raise self._availability_exception
        return self._available

    async def create_event(self, **kwargs) -> str:
        if self._create_exception is not None:
            raise self._create_exception
        self.create_event_calls.append(kwargs)
        return self._create_event_link


_SCHEDULING_CONFIG = SchedulingConfig(
    timezone="America/Sao_Paulo",
    expediente_dias="seg-sex",
    expediente_inicio="09:00",
    expediente_fim="18:00",
)


def setup_function():
    reset_all_booking_slots()


async def test_agendamento_slots_incompletos_pede_dados_sem_chamar_mcp():
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"data_hora": null, "nome": "Maria", "email": null, "telefone": null, "confirmacao": null}',
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "meu nome é Maria",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-1",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)
    assert decisao.domain == "agendamento"
    assert decisao.motivo_escalonamento == "coleta_dados"
    assert "telefone" in decisao.resposta.lower() or "e-mail" in decisao.resposta.lower()
    assert calendar_client.create_event_calls == []


async def test_agendamento_horario_fora_do_expediente_pede_novo_horario():
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "2020-01-01T10:00:00-03:00", "nome": "Maria", '
                '"email": "maria@example.com", "telefone": "11999999999", "confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "quero marcar em 2020",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-2",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "horario_invalido"
    assert calendar_client.create_event_calls == []


async def test_agendamento_horario_em_conflito_pede_novo_horario():
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "2026-10-01T10:00:00-03:00", "nome": "Maria", '
                '"email": "maria@example.com", "telefone": "11999999999", "confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient(available=False)

    eventos = await _coletar_eventos(
        "quero marcar quinta às 10h",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-3",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "horario_invalido"
    assert calendar_client.create_event_calls == []


async def test_agendamento_horario_valido_pede_confirmacao():
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "2026-10-01T10:00:00-03:00", "nome": "Maria", '
                '"email": "maria@example.com", "telefone": "11999999999", "confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient(available=True)

    eventos = await _coletar_eventos(
        "quero marcar quinta às 10h",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-4",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "aguardando_confirmacao"
    assert "confirmar" in decisao.resposta.lower()
    assert calendar_client.create_event_calls == []


async def test_agendamento_confirmacao_cria_evento_e_limpa_slots():
    set_booking_slots(
        "conv-5",
        BookingSlots(
            data_hora=datetime(2026, 10, 1, 10, 0),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"data_hora": null, "nome": null, "email": null, "telefone": null, "confirmacao": true}',
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "sim, pode confirmar",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-5",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "confirmado"
    assert len(calendar_client.create_event_calls) == 1
    assert get_booking_slots("conv-5") == BookingSlots()


async def test_agendamento_falha_do_mcp_na_confirmacao_mantem_slots():
    set_booking_slots(
        "conv-6",
        BookingSlots(
            data_hora=datetime(2026, 10, 1, 10, 0),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"data_hora": null, "nome": null, "email": null, "telefone": null, "confirmacao": true}',
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient(
        create_exception=GoogleCalendarConnectionError("timeout")
    )

    eventos = await _coletar_eventos(
        "sim, pode confirmar",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-6",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "mcp_indisponivel"
    slots_restantes = get_booking_slots("conv-6")
    assert slots_restantes.nome == "Maria"  # dados preservados
    assert slots_restantes.awaiting_confirmation is False  # pode tentar confirmar de novo


async def test_agendamento_resposta_ambigua_durante_confirmacao_volta_a_perguntar():
    set_booking_slots(
        "conv-7",
        BookingSlots(
            data_hora=datetime(2026, 10, 1, 10, 0),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text='{"data_hora": null, "nome": null, "email": null, "telefone": null, "confirmacao": null}',
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "quanto tempo dura a visita?",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-7",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "aguardando_confirmacao"
    assert calendar_client.create_event_calls == []
```

Além disso, ajuste `test_ttft_usa_prompt_eval_duration_nao_load_duration` (usava a mensagem "quero agendar uma visita" só como atalho para garantir `backend_escolhido == "local"` sem depender do RAG — isso quebra com o novo fluxo de agendamento). Troque a mensagem/setup por um domínio que segue o caminho local genérico de verdade:

```python
# backend/tests/test_orchestrator.py — dentro de test_ttft_usa_prompt_eval_duration_nao_load_duration
    rag_client = _FakeRAGClient(documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)])

    eventos = await _coletar_eventos(
        "não funciona, me ajuda",  # domínio "suporte" via keyword, RAG não-vazio → local garantido
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -v`
Expected: FAIL (novos testes com `TypeError: handle_message() got an unexpected keyword argument 'conversation_id'`; testes existentes ainda passam)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/router/orchestrator.py — imports (adicionar)
from app.mcp_client.google_calendar import (
    CalendarClient,
    GoogleCalendarAuthError,
    GoogleCalendarConnectionError,
)
from app.router.scheduling import (
    DURACAO_VISITA,
    MSG_ERRO_MCP,
    HorarioInvalidoError,
    SchedulingConfig,
    clear_booking_slots,
    extract_booking_slots,
    get_booking_slots,
    mensagem_campos_faltando,
    mensagem_pedir_confirmacao,
    mensagem_sucesso,
    merge_slots,
    set_booking_slots,
    validar_expediente,
)
```

```python
# backend/src/app/router/orchestrator.py — atualizar o comentário do campo
# (RouterDecision, campo motivo_escalonamento):
    motivo_escalonamento: str  # "fora_escopo" | "rag_vazio" | "complexidade_alta" | "nenhum"
    # | (agendamento) "coleta_dados" | "horario_invalido" | "aguardando_confirmacao"
    # | "confirmado" | "mcp_indisponivel"
```

```python
# backend/src/app/router/orchestrator.py — nova função privada, antes de
# `handle_message`

async def _emitir_resposta_agendamento(texto: str, motivo: str) -> AsyncIterator[TokenEvent | RouterDecision]:
    yield TokenEvent(text=texto)
    yield RouterDecision(
        domain="agendamento",
        complexity="baixa",
        confidence=1.0,
        complexity_strategy_usada="agendamento",
        backend_escolhido="local",
        motivo_escalonamento=motivo,
        resposta=texto,
        latencia_ms=0.0,
        tokens_entrada=None,
        tokens_saida=None,
        custo_estimado_usd=0.0,
    )


async def _handle_agendamento(
    conversation_id: str,
    message: str,
    recent_messages: list[str],
    local_client: LLMClient,
    calendar_client: CalendarClient,
    scheduling_config: SchedulingConfig,
) -> AsyncIterator[TokenEvent | RouterDecision]:
    slots = get_booking_slots(conversation_id)
    extraction = await extract_booking_slots(message, recent_messages, slots, local_client)
    slots = merge_slots(slots, extraction)

    if not slots.is_complete():
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            mensagem_campos_faltando(slots), "coleta_dados"
        ):
            yield evento
        return

    if not slots.awaiting_confirmation:
        try:
            validar_expediente(slots.data_hora, scheduling_config)
            fim = slots.data_hora + DURACAO_VISITA
            disponivel = await calendar_client.is_time_available(slots.data_hora, fim)
            if not disponivel:
                raise HorarioInvalidoError(
                    "Esse horário já está reservado. Pode sugerir outro horário?"
                )
        except HorarioInvalidoError as exc:
            slots.data_hora = None
            set_booking_slots(conversation_id, slots)
            async for evento in _emitir_resposta_agendamento(exc.motivo, "horario_invalido"):
                yield evento
            return
        except (GoogleCalendarAuthError, GoogleCalendarConnectionError) as exc:
            logger.error(
                "google_calendar_indisponivel",
                extra={
                    "router": {
                        "event": "google_calendar_indisponivel",
                        "etapa": "checagem_disponibilidade",
                        "erro": str(exc),
                    }
                },
            )
            set_booking_slots(conversation_id, slots)
            async for evento in _emitir_resposta_agendamento(MSG_ERRO_MCP, "mcp_indisponivel"):
                yield evento
            return

        slots.awaiting_confirmation = True
        set_booking_slots(conversation_id, slots)
        async for evento in _emitir_resposta_agendamento(
            mensagem_pedir_confirmacao(slots, scheduling_config.timezone), "aguardando_confirmacao"
        ):
            yield evento
        return

    if extraction.confirmacao:
        try:
            fim = slots.data_hora + DURACAO_VISITA
            await calendar_client.create_event(
                summary=f"Visita — {slots.nome}",
                start=slots.data_hora,
                end=fim,
                attendee_email=slots.email,
                attendee_name=slots.nome,
                description=f"Telefone: {slots.telefone}",
            )
        except (GoogleCalendarAuthError, GoogleCalendarConnectionError) as exc:
            logger.error(
                "google_calendar_indisponivel",
                extra={
                    "router": {
                        "event": "google_calendar_indisponivel",
                        "etapa": "criacao_evento",
                        "erro": str(exc),
                    }
                },
            )
            slots.awaiting_confirmation = False
            set_booking_slots(conversation_id, slots)
            async for evento in _emitir_resposta_agendamento(MSG_ERRO_MCP, "mcp_indisponivel"):
                yield evento
            return

        texto = mensagem_sucesso(slots, scheduling_config.timezone)
        clear_booking_slots(conversation_id)
        async for evento in _emitir_resposta_agendamento(texto, "confirmado"):
            yield evento
        return

    # Não confirmou claramente — mantém os slots e volta a pedir confirmação.
    set_booking_slots(conversation_id, slots)
    async for evento in _emitir_resposta_agendamento(
        mensagem_pedir_confirmacao(slots, scheduling_config.timezone), "aguardando_confirmacao"
    ):
        yield evento
```

```python
# backend/src/app/router/orchestrator.py — assinatura de handle_message
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
) -> AsyncIterator[StatusEvent | TokenEvent | RouterDecision]:
```

```python
# backend/src/app/router/orchestrator.py — dentro de handle_message, logo
# após o bloco try/except da classificação (onde hoje começa
# `backend_escolhido = "local"` / `if classification.domain == "agendamento":`),
# substituir por:

    if classification.domain == "agendamento":
        async for evento in _handle_agendamento(
            conversation_id=conversation_id,
            message=message,
            recent_messages=recent_messages,
            local_client=local_client,
            calendar_client=calendar_client,
            scheduling_config=scheduling_config,
        ):
            yield evento
        return

    backend_escolhido = "local"
    motivo = "nenhum"
    documentos: list[Document] = []
    rag_retrieval_ms: float | None = None
    rag_chunks_count: int | None = None
    rag_avg_score: float | None = None
    rag_chunks: list[RagChunkMetric] | None = None

    if classification.domain == "fora_escopo":
        backend_escolhido = "externo"
        motivo = "fora_escopo"
    else:
        # ... (resto do bloco existente sem mudanças)
```

Note que o `if classification.domain == "agendamento": backend_escolhido = "local"` original é removido — substituído pelo bloco acima que já dá `return` antes de chegar no resto da função (RAG/`_build_prompt`/`generate_stream` nunca rodam para este domínio agora).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_orchestrator.py -v`
Expected: PASS (todos os testes do arquivo, novos e existentes)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/orchestrator.py backend/tests/test_orchestrator.py
git commit -m "feat(agendamento): fluxo completo de agendamento no orchestrator (R11, Fase 4A)"
```

---

## Task 10: `playbooks.py` — Remove o playbook morto de agendamento

**Files:**
- Modify: `backend/src/app/router/playbooks.py`
- Modify: `backend/tests/test_playbooks.py`

**Interfaces:**
- Consumes: nada novo.
- Produces: `get_playbook("agendamento")` passa a devolver `None` (mesmo comportamento de `fora_escopo`).

- [ ] **Step 1: Update the test first**

```python
# backend/tests/test_playbooks.py
def test_todos_os_dominios_de_negocio_tem_playbook():
    for domain in ("vendas", "suporte", "atendimento"):
        assert get_playbook(domain) is not None


def test_agendamento_nao_tem_mais_playbook():
    # Desde a Fase 4A, o domínio "agendamento" é tratado por
    # `app.router.orchestrator._handle_agendamento` (máquina de estado
    # própria), sem passar mais por `build_system_prompt`/playbook — ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md.
    assert get_playbook("agendamento") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_playbooks.py -v`
Expected: FAIL em `test_agendamento_nao_tem_mais_playbook` (`get_playbook("agendamento")` ainda devolve a string do playbook antigo)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/router/playbooks.py — remover o bloco
#
#   # Agendamento tem tratamento próprio no orchestrator (sempre local, R11 na
#   # Fase 4). Mantido aqui por completude, mas hoje o orchestrator roteia
#   # agendamento sem passar por contexto de RAG.
#   _AGENDAMENTO_PLAYBOOK = (
#       "Domínio: AGENDAMENTO DE VISITA.\n"
#       ...
#   )
#
# e a entrada "agendamento": _AGENDAMENTO_PLAYBOOK do dict _PLAYBOOKS:

_PLAYBOOKS: dict[Domain, str] = {
    "vendas": _VENDAS_PLAYBOOK,
    "suporte": _SUPORTE_PLAYBOOK,
    "atendimento": _ATENDIMENTO_PLAYBOOK,
}
```

Atualize também o docstring do módulo (topo do arquivo), que hoje menciona "Vendas e Agendamento terão ferramentas de ação... nas Fases 4-5" — ajuste para refletir que Agendamento (Fase 4A) já não passa mais por playbook:

```python
# backend/src/app/router/playbooks.py — docstring do módulo
"""Playbooks e prompts de sistema por domínio de atendimento (R7, Fase 3).

Cada domínio de atendimento tem um "playbook" — um bloco de instruções de
sistema que orienta o tom e o procedimento da resposta do LLM. O
orchestrator antepõe o playbook do domínio classificado ao prompt (com ou
sem contexto de RAG) antes de chamar o modelo.

# MVP: playbooks são strings estáticas por domínio, sem versionamento nem
# edição em runtime (ver docs/ARCHITECTURE.md §3-4 — assimetria intencional
# entre domínios). Suporte Técnico e Atendimento ao Usuário são resolvidos
# por LLM + RAG, sem camada de ação (ticketing é evolução futura). Vendas
# tem ferramenta de ação na Fase 5 (MCP B2B); por ora o playbook de Vendas
# apenas *oferece proativamente* o agendamento de visita quando há intenção
# de compra. Agendamento (Fase 4A, R11) NÃO usa playbook — é tratado
# inteiramente por `app.router.orchestrator._handle_agendamento` e
# `app.router.scheduling`, uma máquina de estado própria em vez de um
# prompt de sistema (ver
# docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md).
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_playbooks.py -v`
Expected: PASS (todos os testes do arquivo)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/router/playbooks.py backend/tests/test_playbooks.py
git commit -m "refactor(agendamento): remove playbook morto — fluxo é tratado por scheduling.py (R11, Fase 4A)"
```

---

## Task 11: `main.py` e `chat.py` — Injeção de dependências

**Files:**
- Modify: `backend/src/app/main.py`
- Modify: `backend/src/app/api/chat.py`
- Modify: `backend/tests/test_main_app.py`

**Interfaces:**
- Consumes: `GoogleCalendarMCPClient` (Task 6), `SchedulingConfig` (Task 3), `Settings` (Task 8).
- Produces: `app.state.calendar_client: GoogleCalendarMCPClient`; `app.state.scheduling_config: SchedulingConfig`; `chat.get_calendar_client`/`chat.get_scheduling_config` (dependências FastAPI).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_main_app.py (adicionar)
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.router.scheduling import SchedulingConfig


def test_create_app_monta_o_cliente_de_calendario_e_config_de_agendamento():
    app = create_app()

    assert isinstance(app.state.calendar_client, GoogleCalendarMCPClient)
    assert isinstance(app.state.scheduling_config, SchedulingConfig)
    assert app.state.scheduling_config.timezone == "America/Sao_Paulo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_main_app.py -v -k calendario`
Expected: FAIL com `AttributeError: 'State' object has no attribute 'calendar_client'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/app/main.py — imports (adicionar)
from app.mcp_client.google_calendar import GoogleCalendarMCPClient
from app.router.scheduling import SchedulingConfig
```

```python
# backend/src/app/main.py — dentro de create_app(), logo após o bloco do
# app.state.stt_client (fim da função, antes de app.include_router(...))
    # MCP do Google Calendar (R11, Fase 4A) — carregamento de
    # credenciais/refresh token é lazy (só no primeiro uso real), então
    # construir o cliente aqui não exige que os arquivos já existam em todo
    # ambiente de dev (ver
    # docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md §3).
    app.state.calendar_client = GoogleCalendarMCPClient(
        credentials_path=settings.google_calendar_credentials_path,
        token_path=settings.google_calendar_token_path,
        calendar_id=settings.google_calendar_calendar_id,
    )
    app.state.scheduling_config = SchedulingConfig(
        timezone=settings.agendamento_timezone,
        expediente_dias=settings.agendamento_expediente_dias,
        expediente_inicio=settings.agendamento_expediente_inicio,
        expediente_fim=settings.agendamento_expediente_fim,
    )
```

```python
# backend/src/app/api/chat.py — imports (adicionar)
from app.mcp_client.google_calendar import CalendarClient
from app.router.scheduling import SchedulingConfig
```

```python
# backend/src/app/api/chat.py — novas dependências, junto das outras
# funções get_*(request: Request) já existentes
def get_calendar_client(request: Request) -> CalendarClient:
    return request.app.state.calendar_client


def get_scheduling_config(request: Request) -> SchedulingConfig:
    return request.app.state.scheduling_config
```

```python
# backend/src/app/api/chat.py — assinatura de send_message (adicionar
# parâmetros)
    calendar_client: CalendarClient = Depends(get_calendar_client),
    scheduling_config: SchedulingConfig = Depends(get_scheduling_config),
```

```python
# backend/src/app/api/chat.py — dentro de event_stream(), na chamada a
# handle_message(...), acrescentar:
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
            ):
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_main_app.py tests/test_chat_api.py -v`
Expected: PASS (todos os testes de ambos os arquivos — `test_chat_api.py` não deveria quebrar, já que os novos parâmetros de `send_message` têm `Depends` resolvíveis a partir de `app.state`, mesmo padrão dos demais)

- [ ] **Step 5: Commit**

```bash
git add backend/src/app/main.py backend/src/app/api/chat.py backend/tests/test_main_app.py
git commit -m "feat(agendamento): injeta cliente MCP do Calendar e config de agendamento no chat (R11, Fase 4A)"
```

---

## Task 12: Suíte completa, `.env.example`/`docs/ROADMAP.md` e commit final

**Files:**
- Modify: `docs/ROADMAP.md`

- [ ] **Step 1: Rodar a suíte inteira do backend**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: todos os testes passam (os já existentes antes deste plano + todos os novos dos Tasks 1-11)

- [ ] **Step 2: Rodar lint**

Run: `cd backend && source .venv/bin/activate && ruff check . && ruff format --check .`
Expected: sem erros (rodar `ruff format .` antes se houver diffs de formatação pendentes, e commitar antes deste passo — ver `docs/CONVENTIONS.md`)

- [ ] **Step 3: Marcar os itens de R11 em `docs/ROADMAP.md`**

Na Fase 4 (`## Fase 4 — Agendamento via MCP e Monitor de Tom (R8, R11)`), marcar como concluídos:

```markdown
- [x] Implementar cliente MCP para o Google Calendar
- [x] Implementar nova intenção de agendamento no roteador (coleta de
      data/hora e dados básicos na conversa)
- [x] Implementar confirmação automática por e-mail após criar o evento
- [x] Implementar tratamento de erro claro para falha de conexão/autenticação
      do MCP do Google Calendar (sugerir nova tentativa ou transferir para
      atendente)
```

Deixe os dois últimos itens da Fase 4 (classificador de sentimento/urgência e transferência simulada, R8) como `- [ ]` — são o escopo da Fase 4B, fora deste plano (ver spec §1).

Adicione uma nota curta logo abaixo do cabeçalho da Fase 4, no mesmo estilo das notas já usadas em outras fases, explicando a decomposição:

```markdown
> R11 (agendamento via MCP Calendar) implementado como Fase 4A — ver
> `docs/superpowers/specs/2026-09-21-agendamento-mcp-calendar-design.md`.
> R8 (monitor de tom) é a Fase 4B, com spec própria ainda a escrever.
```

- [ ] **Step 4: Commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): marca agendamento via MCP Calendar como concluído (R11, Fase 4A)"
```

---

## Self-Review

**Cobertura da spec:**
- §2 (qual MCP consumir) → Task 6 (`_CALENDAR_MCP_URL`, Streamable HTTP).
- §3 (autenticação/consentimento único) → Tasks 4, 5, 7.
- §4/§4.1/§4.2 (coleta de dados e fluxo) → Tasks 1, 2, 9.
- §4.3 (validação de horário) → Task 3, 9.
- §5 (`GoogleCalendarMCPClient`) → Tasks 4, 5, 6.
- §6 (tratamento de erro) → Task 9 (`google_calendar_indisponivel`, `MSG_ERRO_MCP`).
- §7 (testes) → todas as tasks têm testes mockados, sem rede real.
- §8 (`.env.example`) → Task 8.
- §9 (não-objetivos) → nenhuma task implementa reagendamento, múltiplas agendas, `suggest_time`, SMS ou servidor MCP próprio — confirmado por ausência deliberada.

**Type consistency:** `BookingSlots`/`SchedulingConfig`/`SlotExtractionResult` definidos no Task 1/2/3 são usados com os mesmos nomes de campo em todas as tasks seguintes (`data_hora`, `nome`, `email`, `telefone`, `awaiting_confirmation`, `timezone`, `expediente_dias`, `expediente_inicio`, `expediente_fim`, `confirmacao`). `CalendarClient`/`GoogleCalendarAuthError`/`GoogleCalendarConnectionError` (Task 4) usados consistentemente nas Tasks 5, 6, 9, 11.

**Placeholders:** nenhum "TBD"/"implementar depois" — a única ressalva documentada é a nota inline no Task 6 sobre nomes exatos de parâmetros da tool MCP precisarem de confirmação contra o endpoint real na primeira execução (já registrada como tal na spec §2, não é um buraco de implementação).
