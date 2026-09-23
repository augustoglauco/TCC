import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.logging_config import JsonFormatter
from app.mcp_client.google_calendar import GoogleCalendarConnectionError
from app.models.chat import RagChunkMetric
from app.router.llm_client import LLMResponse, LLMStreamChunk
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.rag_client import Document, RAGConnectionError
from app.router.scheduling import (
    BookingSlots,
    SchedulingConfig,
    get_booking_slots,
    reset_all_booking_slots,
    set_booking_slots,
)


class _FakeLLMClient:
    def __init__(
        self,
        response: LLMResponse | None = None,
        exception: Exception | None = None,
        model_ready: bool = True,
        model_ready_exception: Exception | None = None,
    ) -> None:
        self._response = response
        self._exception = exception
        self._model_ready = model_ready
        self._model_ready_exception = model_ready_exception
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
        if self._model_ready_exception is not None:
            raise self._model_ready_exception
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


class _FakeLLMClientComJev(_FakeLLMClient):
    """`_FakeLLMClient` com `classify_intent_jev` — usada como
    `external_client` nos testes de telemetria de `provider_efetivo` (Fix
    revisão final, achado importante 1) que precisam de um provedor Jev que
    REALMENTE responde, ao contrário de `_FakeLLMClient` puro (sem esse
    método, sempre cai no fallback heurístico dentro de
    `_classify_with_jev`)."""

    def __init__(
        self,
        *args,
        jev_domain: str = "vendas",
        jev_confidence: float = 0.9,
        jev_fail: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._jev_domain = jev_domain
        self._jev_confidence = jev_confidence
        self._jev_fail = jev_fail

    async def classify_intent_jev(self, message: str, recent_messages: list[str] | None = None):
        if self._jev_fail:
            raise RuntimeError("Conexão com OpenRouter falhou")
        return self._jev_domain, self._jev_confidence


class _FakeRAGClient:
    def __init__(
        self,
        documents: list[Document] | None = None,
        documents_sequence: list[list[Document]] | None = None,
        exception: Exception | None = None,
    ) -> None:
        self._documents = documents if documents is not None else []
        self._documents_sequence = documents_sequence
        self._exception = exception
        self.queries: list[str] = []

    async def search(self, query: str, domain: str) -> list[Document]:
        self.queries.append(query)
        if self._exception is not None:
            raise self._exception
        if self._documents_sequence is not None:
            index = len(self.queries) - 1
            if index < len(self._documents_sequence):
                return self._documents_sequence[index]
            return self._documents_sequence[-1]
        return self._documents


def _resposta_local() -> LLMResponse:
    return LLMResponse(text="resposta local", total_duration_ms=100.0)


def _resposta_externa() -> LLMResponse:
    return LLMResponse(text="resposta externa", total_duration_ms=200.0)


async def _coletar_eventos(message, **kwargs):
    return [evento async for evento in handle_message(message, **kwargs)]


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


def _data_futura_valida() -> datetime:
    """Um dia útil (seg-sex) bem no futuro, às 10h, com fuso horário aplicado
    (`America/Sao_Paulo`, o mesmo de `_SCHEDULING_CONFIG`) — dentro do
    expediente configurado (09:00-18:00). Computado em cima de
    `datetime.now()` em vez de hardcodado, para não "apodrecer": uma data
    fixa como "2026-10-01" passa a ser rejeitada por `validar_expediente`
    (horário no passado) assim que o calendário andar até lá.

    # Fix (revisão final, achado 3): antes, este helper devolvia um datetime
    # NAIVE — os testes que pré-populam `BookingSlots` diretamente com ele
    # (em vez de passar pela extração LLM, que já produz datetime aware a
    # partir do ISO8601 com offset) certificavam sem querer o caso quebrado
    # de um `.isoformat()` sem offset UTC chegando às chamadas do MCP.
    # `validar_expediente`/`_validar_horario_para_agendamento` normalizam
    # isso de qualquer forma agora, mas o helper devolver aware por padrão
    # reflete o que um sistema correto realmente envia ao MCP.
    """
    referencia = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(days=365)
    while referencia.weekday() > 4:  # 0=segunda ... 4=sexta
        referencia += timedelta(days=1)
    return referencia.replace(hour=10, minute=0, second=0, microsecond=0)


def _data_futura_valida_iso() -> str:
    # America/Sao_Paulo não observa horário de verão desde 2019 — deslocamento
    # fixo -03:00, seguro de hardcodar aqui.
    return _data_futura_valida().strftime("%Y-%m-%dT%H:%M:%S-03:00")


async def test_agendamento_slots_incompletos_pede_dados_sem_chamar_mcp():
    # Continuação de um fluxo já em andamento: o visitante já informou a
    # data/hora num turno anterior (slots parciais já salvos para a
    # conversa) e agora informa o nome. A mensagem em si ("meu nome é
    # Maria") não contém nenhuma palavra-chave de domínio — é a presença de
    # slots parciais para `conversation_id` que mantém o roteador no fluxo
    # de agendamento (ver gatilho em `handle_message`).
    set_booking_slots(
        "conv-1",
        BookingSlots(data_hora=_data_futura_valida()),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": null, "nome": "Maria", "email": null, "telefone": null, '
                '"confirmacao": null}'
            ),
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
                '{"data_hora": "' + _data_futura_valida_iso() + '", "nome": "Maria", '
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
                '{"data_hora": "' + _data_futura_valida_iso() + '", "nome": "Maria", '
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
            data_hora=_data_futura_valida(),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": null, "nome": null, "email": null, "telefone": null, '
                '"confirmacao": true}'
            ),
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
    # Achado 3 da revisão final: o datetime passado ao MCP precisa ter fuso
    # horário (aware) — um naive `.isoformat()` não tem offset UTC, inválido
    # para a API do Google Calendar.
    chamada = calendar_client.create_event_calls[0]
    assert chamada["start"].tzinfo is not None
    assert chamada["end"].tzinfo is not None


async def test_agendamento_confirmacao_com_nova_data_invalida_revalida_antes_de_criar_evento():
    # Achado crítico 1 da revisão final: uma mensagem que confirma E muda a
    # data ao mesmo tempo ("sim, pode confirmar, mas prefiro em 2020") não
    # pode pular a validação de horário só porque `confirmacao=True` —
    # `merge_slots` já aplicou a nova `data_hora` extraída desta mesma
    # mensagem antes deste ponto do fluxo (o horário original, válido,
    # nunca chega a ser usado). A nova data extraída está no passado/fora do
    # expediente — a resposta deve ser `horario_invalido`, e `create_event`
    # nunca deve ser chamado.
    set_booking_slots(
        "conv-11",
        BookingSlots(
            data_hora=_data_futura_valida(),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "2020-01-01T10:00:00-03:00", "nome": null, "email": null, '
                '"telefone": null, "confirmacao": true}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "sim, pode confirmar, mas na verdade prefiro em 2020",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-11",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "horario_invalido"
    assert calendar_client.create_event_calls == []


async def test_agendamento_falha_do_mcp_na_confirmacao_mantem_slots():
    set_booking_slots(
        "conv-6",
        BookingSlots(
            data_hora=_data_futura_valida(),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": null, "nome": null, "email": null, "telefone": null, '
                '"confirmacao": true}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient(create_exception=GoogleCalendarConnectionError("timeout"))

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
            data_hora=_data_futura_valida(),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": null, "nome": null, "email": null, "telefone": null, '
                '"confirmacao": null}'
            ),
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


async def test_agendamento_resposta_ambigua_muda_para_horario_invalido_revalida_no_mesmo_turno():
    # Regressão (fix-round Task 9, achado 3): durante awaiting_confirmation,
    # uma resposta ambígua que também muda data_hora (em vez de confirmar
    # claramente) não pode simplesmente repetir "posso confirmar?" sobre um
    # horário que deixou de ser válido — precisa revalidar antes de pedir
    # confirmação de novo (spec §4.1 passo 7). Aqui a nova data_hora
    # extraída é no passado (2020), então a resposta já deve vir como
    # "horario_invalido" no mesmo turno, sem re-perguntar "posso confirmar?"
    # e sem chamar create_event.
    set_booking_slots(
        "conv-8",
        BookingSlots(
            data_hora=_data_futura_valida(),
            nome="Maria",
            email="maria@example.com",
            telefone="11999999999",
            awaiting_confirmation=True,
        ),
    )
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "2020-01-01T10:00:00-03:00", "nome": null, "email": null, '
                '"telefone": null, "confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "na verdade prefiro em 2020",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-8",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "horario_invalido"
    assert calendar_client.create_event_calls == []


async def test_agendamento_falha_do_mcp_na_checagem_de_disponibilidade_mantem_slots():
    # Regressão (fix-round Task 9, achado 1): o except de
    # GoogleCalendarAuthError/GoogleCalendarConnectionError no ponto de
    # checagem de disponibilidade (is_time_available) não tinha cobertura de
    # teste — só o except homônimo em create_event tinha.
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": "' + _data_futura_valida_iso() + '", "nome": "Maria", '
                '"email": "maria@example.com", "telefone": "11999999999", "confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient(
        availability_exception=GoogleCalendarConnectionError("timeout")
    )

    eventos = await _coletar_eventos(
        "quero marcar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-9",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
    )

    decisao = eventos[-1]
    assert decisao.motivo_escalonamento == "mcp_indisponivel"
    slots_restantes = get_booking_slots("conv-9")
    assert slots_restantes.nome == "Maria"  # dados preservados
    assert calendar_client.create_event_calls == []


async def test_agendamento_falha_do_local_na_extracao_vira_local_backend_indisponivel():
    # Regressão (fix-round Task 9, achado 2): a chamada a
    # extract_booking_slots (que usa o LLM local) não era protegida por
    # try/except, ao contrário de toda outra chamada ao backend local neste
    # arquivo (classificação, geração) — uma falha do Ollama no meio do
    # fluxo de agendamento vazava crua em vez de virar
    # LocalBackendIndisponivelError.
    local_client = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    calendar_client = _FakeCalendarClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "quero marcar uma visita",
            recent_messages=[],
            local_client=local_client,
            external_client=_FakeLLMClient(response=_resposta_externa()),
            rag_client=_FakeRAGClient(),
            complexity_strategy="heuristic",
            conversation_id="conv-10",
            calendar_client=calendar_client,
            scheduling_config=_SCHEDULING_CONFIG,
        )


async def test_handle_message_propaga_router_provider_jev_quando_client_falha():
    # Fix (revisão final, achado importante 1) — REGRESSÃO do bug corrigido
    # nesta rodada: `intent_router_provider="jev_openrouter"` é pedido, mas
    # o `_FakeLLMClient` usado como `external_client` não tem
    # `classify_intent_jev`, então `_classify_with_jev` degrada
    # silenciosamente para a heurística local (comportamento já coberto
    # pelos testes do classifier). Antes do fix, `RouterDecision.router_provider`
    # vinha direto do parâmetro bruto `intent_router_provider` e mentia
    # "jev_openrouter" mesmo quando a heurística respondeu de fato. Agora
    # deve refletir `classification.provider_efetivo`, ou seja
    # "heuristica_llm" — ver também o teste de sucesso logo abaixo.
    eventos = await _coletar_eventos(
        "Quero orçamento",
        recent_messages=[],
        local_client=_FakeLLMClient(response=_resposta_local()),
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        intent_router_provider="jev_openrouter",
    )

    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)
    assert decisao.router_provider == "heuristica_llm"


async def test_handle_message_propaga_router_provider_jev_quando_client_sucede():
    # Contraparte do teste acima: quando o Jev de fato responde (client com
    # `classify_intent_jev` funcional), `RouterDecision.router_provider`
    # deve ser "jev_openrouter" — o provedor que realmente classificou.
    external_client = _FakeLLMClientComJev(
        response=_resposta_externa(), jev_domain="vendas", jev_confidence=0.9
    )
    eventos = await _coletar_eventos(
        "Quero orçamento",
        recent_messages=[],
        local_client=_FakeLLMClient(response=_resposta_local()),
        external_client=external_client,
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        intent_router_provider="jev_openrouter",
    )

    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)
    assert decisao.router_provider == "jev_openrouter"


async def test_router_provider_default_e_heuristica_llm():
    # Sem passar `intent_router_provider`, o default do parâmetro deve
    # aparecer no RouterDecision (compatibilidade retroativa com chamadores
    # existentes, ex.: testes de agendamento que não conhecem o provider).
    eventos = await _coletar_eventos(
        "Quero orçamento",
        recent_messages=[],
        local_client=_FakeLLMClient(response=_resposta_local()),
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
    )

    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)
    assert decisao.router_provider == "heuristica_llm"


async def test_agendamento_propaga_router_provider_no_fluxo_de_coleta():
    # Ruling do controlador (Task 4): o fluxo de agendamento constrói seus
    # próprios RouterDecision via `_emitir_resposta_agendamento`, chamado a
    # partir de `_handle_agendamento` — sem threading explícito do provider
    # por esses dois helpers, essas decisões usariam sempre o default do
    # campo em vez do provider realmente configurado para a requisição.
    local_client = _FakeLLMClient(
        response=LLMResponse(
            text=(
                '{"data_hora": null, "nome": "Maria", "email": null, "telefone": null, '
                '"confirmacao": null}'
            ),
            total_duration_ms=10.0,
        )
    )
    calendar_client = _FakeCalendarClient()

    eventos = await _coletar_eventos(
        "quero marcar uma visita",
        recent_messages=[],
        local_client=local_client,
        external_client=_FakeLLMClient(response=_resposta_externa()),
        rag_client=_FakeRAGClient(),
        complexity_strategy="heuristic",
        conversation_id="conv-router-provider",
        calendar_client=calendar_client,
        scheduling_config=_SCHEDULING_CONFIG,
        intent_router_provider="jev_openrouter",
    )

    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)
    assert decisao.domain == "agendamento"
    assert decisao.router_provider == "jev_openrouter"


async def test_ttft_usa_prompt_eval_duration_nao_load_duration():
    # `load_duration` é o tempo de carregar o MODELO na memória (~0 após o
    # primeiro uso) — não deve ser usado como TTFT. `prompt_eval_duration` é
    # o proxy correto (tempo de processar o prompt antes de gerar tokens).
    resposta = LLMResponse(
        text="resposta local",
        completion_tokens=100,
        total_duration_ms=2500.0,
        load_duration_ms=500.0,
        prompt_eval_duration_ms=150.0,
        eval_duration_ms=1800.0,
    )
    local_client = _FakeLLMClient(response=resposta)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    eventos = await _coletar_eventos(
        "não funciona, me ajuda",  # domínio "suporte" via keyword, RAG não-vazio → local garantido
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.ttft_ms == 150.0
    # TPS usa eval_duration (geração pura): 100 tokens / 1.8s = 55.56
    assert decisao.tps == pytest.approx(55.56, abs=0.01)


async def test_fora_escopo_sempre_externo_sem_tentar_rag():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("não deveria ser chamado"))

    eventos = await _coletar_eventos(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.domain == "fora_escopo"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "fora_escopo"
    assert local_client.calls == 0
    assert external_client.calls == 1


async def test_rag_vazio_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.domain == "vendas"
    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "rag_vazio"


async def test_rag_vazio_sem_historico_nao_tenta_de_novo():
    # Primeira mensagem da conversa (recent_messages vazio) — não há
    # contexto pra concatenar, então só uma busca deve ocorrer (mesmo
    # comportamento de antes desta mudança).
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.motivo_escalonamento == "rag_vazio"
    assert rag_client.queries == ["Qual o preço desse produto?"]


async def test_rag_vazio_com_historico_tenta_de_novo_com_contexto_e_acha():
    # Mensagem de acompanhamento ("quais outras opções?") sozinha não bate
    # com nada no RAG — a segunda tentativa, com o histórico concatenado,
    # encontra o documento e mantém a resposta local (regressão do bug
    # relatado: "perguntei sobre câmeras, [...] perguntei sobre outras
    # opções e ele simplesmente roteou para externo").
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(content="câmera VHD 5830", source="catalogo", score=0.8)
    rag_client = _FakeRAGClient(documents_sequence=[[], [documento]])

    # MVP: precisa de uma palavra-chave (aqui "produto") pra classificação
    # heurística acertar o domínio "vendas" sem depender de uma chamada real
    # de LLM — o ponto do teste é o fallback de RAG, não o classificador.
    eventos = await _coletar_eventos(
        "quais outras opções de produto vocês têm?",
        recent_messages=["você teria alguma câmera de boa resolução?"],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert rag_client.queries == [
        "quais outras opções de produto vocês têm?",
        "você teria alguma câmera de boa resolução?\nquais outras opções de produto vocês têm?",
    ]


async def test_rag_com_resultado_na_primeira_busca_nao_tenta_de_novo():
    # Busca direta já encontrou algo — não deve concatenar o histórico e
    # gastar uma segunda busca (evita diluir o embedding sem necessidade).
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(content="...", source="catalogo", score=0.9)
    rag_client = _FakeRAGClient(documents=[documento])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=["mensagem anterior qualquer"],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.motivo_escalonamento == "nenhum"
    assert rag_client.queries == ["Qual o preço desse produto?"]


async def test_rag_com_resultado_e_complexidade_baixa_fica_local():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    eventos = await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "local"
    assert decisao.motivo_escalonamento == "nenhum"
    assert decisao.rag_chunks == [RagChunkMetric(source="catalogo", score=0.9)]


async def test_documento_recuperado_pelo_rag_e_injetado_no_prompt_do_llm():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    documento = Document(
        content="O gerador GD-30 tem potência de 30 kVA.",
        source="catalogo_geradores.txt",
        score=0.9,
    )
    rag_client = _FakeRAGClient(documents=[documento])

    await _coletar_eventos(
        "Qual o preço do gerador GD-30?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert local_client.calls == 1
    assert documento.content in local_client.last_prompt
    assert "Qual o preço do gerador GD-30?" in local_client.last_prompt
    # O playbook do domínio (vendas) é anteposto ao contexto de RAG (Fase 3).
    assert "Domínio: VENDAS" in local_client.last_prompt


async def test_rag_vazio_nao_injeta_contexto_prompt_e_a_mensagem_original():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    await _coletar_eventos(
        "Qual o preço desse produto?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    # Sem documentos, não há bloco de contexto de RAG no prompt — mas, como
    # a mensagem foi classificada em um domínio de negócio (vendas), o
    # playbook do domínio (Fase 3) é anteposto mesmo escalando ao externo.
    # O texto de "Informações recuperadas" (contexto de RAG) NÃO aparece.
    assert "Qual o preço desse produto?" in external_client.last_prompt
    assert "Informações recuperadas" not in external_client.last_prompt
    assert "Domínio: VENDAS" in external_client.last_prompt


async def test_fora_escopo_sem_playbook_envia_apenas_a_mensagem():
    # Mensagem sem palavra-chave de domínio → fora_escopo → sem playbook.
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[])

    await _coletar_eventos(
        "Bom dia, tudo bem com você?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    # fora_escopo não tem playbook e não houve RAG: o prompt reduz à mensagem.
    assert external_client.last_prompt == "Mensagem do cliente: Bom dia, tudo bem com você?"


async def test_rag_com_resultado_e_complexidade_alta_escala_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    mensagem_longa = "Preciso de um orçamento detalhado. " * 10 + " qual o preço?"

    eventos = await _coletar_eventos(
        mensagem_longa,
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )
    decisao = eventos[-1]
    assert isinstance(decisao, RouterDecision)

    assert decisao.backend_escolhido == "externo"
    assert decisao.motivo_escalonamento == "complexidade_alta"


async def test_rag_indisponivel_propaga_erro_sem_fallback_para_externo():
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(exception=RAGConnectionError("qdrant fora do ar"))

    with pytest.raises(RAGConnectionError):
        await _coletar_eventos(
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
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "não funciona, me ajuda",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_falha_de_rede_em_is_model_ready_vira_local_backend_indisponivel():
    # Regressão: `is_model_ready()` faz uma chamada de rede (ex.: GET
    # /api/ps do Ollama) tão sujeita a falha de infraestrutura quanto
    # `generate_stream` — antes da correção, uma falha aqui propagava crua
    # em vez de virar LocalBackendIndisponivelError (e, no endpoint HTTP, em
    # vez de virar o evento SSE `error`).
    local_client = _FakeLLMClient(
        response=_resposta_local(), model_ready_exception=ConnectionError("ollama fora do ar")
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "não funciona, me ajuda",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    assert external_client.calls == 0


async def test_falha_do_local_na_classificacao_llm_nao_faz_fallback_para_externo():
    # Regressão: com strategy="llm" o classificador chama o backend local.
    # Se o Ollama estiver fora do ar, isso é falha de infraestrutura local e
    # deve virar LocalBackendIndisponivelError — nunca degradar em silêncio
    # para fora_escopo (que rotearia para o backend externo).
    local_client = _FakeLLMClient(exception=ConnectionError("ollama fora do ar"))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient()

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="llm",
        )

    assert external_client.calls == 0


async def test_log_de_decisao_tem_campos_json_de_primeiro_nivel(caplog):
    local_client = _FakeLLMClient(response=_resposta_local())
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    with caplog.at_level(logging.INFO, logger="app.router.orchestrator"):
        await _coletar_eventos(
            "não funciona, me ajuda",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )

    registros = [r for r in caplog.records if r.getMessage() == "router_decision"]
    assert len(registros) == 1

    payload = json.loads(JsonFormatter().format(registros[0]))

    assert payload["message"] == "router_decision"
    assert payload["domain"] == "suporte"
    assert payload["backend_escolhido"] == "local"
    assert payload["motivo_escalonamento"] == "nenhum"
    assert payload["custo_estimado_usd"] == 0.0
    assert payload["latencia_ms"] == 100.0


def test_json_formatter_nao_deixa_extra_sobrescrever_campos_base():
    record = logging.LogRecord(
        name="app.router.orchestrator",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="router_decision",
        args=(),
        exc_info=None,
    )
    record.router = {"message": "invasor", "level": "invasor", "domain": "vendas"}

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "router_decision"
    assert payload["level"] == "INFO"
    assert payload["domain"] == "vendas"


async def test_generate_stream_sem_chunk_final_vira_local_backend_indisponivel():
    # Regressão: se `generate_stream` esgotar sem nunca emitir um chunk
    # `done=True` (ex.: Ollama fecha a conexão no meio do cold-start), antes
    # da correção isso escapava como `AssertionError` cru em vez de virar
    # `LocalBackendIndisponivelError` (e, no endpoint HTTP, o evento SSE
    # `error`).
    class _StreamSemChunkFinal:
        def __init__(self) -> None:
            self.calls = 0

        async def is_model_ready(self) -> bool:
            return True

        async def generate_stream(self, prompt: str):
            self.calls += 1
            yield LLMStreamChunk(text="parcial")
            return
            yield  # pragma: no cover - nunca alcançado, só p/ ser async generator

    local_client = _StreamSemChunkFinal()
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    with pytest.raises(LocalBackendIndisponivelError):
        await _coletar_eventos(
            "não funciona, me ajuda",
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
        await _coletar_eventos(
            "Qual a capital da França?",
            recent_messages=[],
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy="heuristic",
        )


async def test_modelo_local_nao_carregado_emite_status_antes_dos_tokens():
    local_client = _FakeLLMClient(response=_resposta_local(), model_ready=False)
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    eventos = await _coletar_eventos(
        "não funciona, me ajuda",
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
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    eventos = await _coletar_eventos(
        "não funciona, me ajuda",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="heuristic",
    )

    assert not any(isinstance(e, StatusEvent) for e in eventos)


async def test_modelo_carrega_durante_classificacao_llm_ainda_assim_emite_status():
    # Reproduz o bug relatado pelo usuário: com strategy="llm", quando a
    # mensagem é ambígua para o classificador por palavra-chave,
    # `classify()` chama `local_client.generate()` (bloqueante) — no Ollama
    # real, é essa chamada (não a geração da resposta em si) que
    # efetivamente paga o cold-start do modelo. Antes desta correção, o
    # único check de `is_model_ready()` ficava logo antes de
    # `generate_stream`, ou seja, DEPOIS do cold-start já ter acontecido em
    # silêncio durante a classificação — o evento `status` nunca era
    # emitido, mesmo a espera real tendo ocorrido (é o que o Fake abaixo
    # simula: `is_model_ready` só volta a `True` depois da primeira
    # chamada, igual o Ollama depois que `generate()` carrega o modelo).
    class _FakeLLMClientCargaNaClassificacao(_FakeLLMClient):
        async def is_model_ready(self) -> bool:
            return self.calls > 0

    local_client = _FakeLLMClientCargaNaClassificacao(
        response=LLMResponse(
            text='{"domain": "suporte", "complexity": "baixa", "confidence": 0.9}',
            total_duration_ms=100.0,
        )
    )
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(documents=[Document(content="...", source="catalogo", score=0.9)])

    eventos = await _coletar_eventos(
        "Qual a capital da França?",
        recent_messages=[],
        local_client=local_client,
        external_client=external_client,
        rag_client=rag_client,
        complexity_strategy="llm",
    )

    assert isinstance(eventos[0], StatusEvent)
    assert eventos[0].status == "carregando_modelo"


async def test_tokens_emitidos_em_ordem_e_resposta_final_e_a_concatenacao():
    local_client = _FakeLLMClient(response=LLMResponse(text="Boa tarde!", total_duration_ms=50.0))
    external_client = _FakeLLMClient(response=_resposta_externa())
    rag_client = _FakeRAGClient(
        documents=[Document(content="conteúdo", source="doc1.txt", score=0.9)]
    )

    eventos = await _coletar_eventos(
        "não funciona, me ajuda",
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
