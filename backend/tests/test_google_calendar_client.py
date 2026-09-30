from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import pytest

import app.mcp_client.google_calendar as google_calendar_module
from app.mcp_client.google_calendar import GoogleCalendarConnectionError, GoogleCalendarMCPClient


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
    async def factory():
        yield session

    return factory


def _client(session: _FakeMCPSession) -> GoogleCalendarMCPClient:
    return GoogleCalendarMCPClient(
        mcp_server_url="http://127.0.0.1:8090/mcp",
        calendar_id="primary",
        session_factory=_fake_session_factory(session),
    )


async def test_default_session_factory_aplica_timeout_configurado(monkeypatch):
    """Achado na revisão de robustez da Fase 9 (docs/ROADMAP.md): sem passar
    `timeout` explícito, `create_mcp_http_client` usa o timeout de leitura
    padrão do SDK `mcp` (300s) — um `calendar-mcp-server` travado poderia
    prender um turno de agendamento por minutos. `timeout_s` do construtor
    precisa chegar de fato ao `httpx.AsyncClient` usado pela sessão MCP."""
    capturado: dict = {}

    @asynccontextmanager
    async def fake_create_mcp_http_client(timeout=None, **kwargs):
        capturado["timeout"] = timeout
        yield object()

    @asynccontextmanager
    async def fake_streamable_http_client(url, http_client=None):
        yield (object(), object())

    class _FakeSession:
        async def initialize(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

    monkeypatch.setattr(
        google_calendar_module, "create_mcp_http_client", fake_create_mcp_http_client
    )
    monkeypatch.setattr(
        google_calendar_module, "streamable_http_client", fake_streamable_http_client
    )
    monkeypatch.setattr(
        google_calendar_module, "ClientSession", lambda *args, **kwargs: _FakeSession()
    )

    client = GoogleCalendarMCPClient(
        mcp_server_url="http://127.0.0.1:8090/mcp", calendar_id="primary", timeout_s=7.5
    )
    async with client._session_factory():
        pass

    assert capturado["timeout"] == httpx.Timeout(7.5)


async def test_is_time_available_true_quando_nao_ha_eventos():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"count": 0, "events": []})
    )
    client = _client(session)

    disponivel = await client.is_time_available(
        datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30)
    )

    assert disponivel is True
    nome_tool, argumentos = session.calls[0]
    assert nome_tool == "find_events"
    assert argumentos["calendar_id"] == "primary"
    assert argumentos["time_min"] == "2026-09-24T10:00:00"
    assert argumentos["time_max"] == "2026-09-24T10:30:00"


async def test_is_time_available_true_quando_ha_apenas_eventos_de_outros_assuntos():
    # Eventos que não são do sistema (sem tag nem prefixo [Sistema]) não devem bloquear
    session = _FakeMCPSession(
        result=_FakeCallToolResult(
            structured_content={
                "count": 1,
                "events": [
                    {
                        "id": "evt_externo",
                        "summary": "Reunião de Planejamento Financeiro",
                        "description": "Alinhamento com diretoria",
                    }
                ],
            }
        )
    )
    client = _client(session)

    disponivel = await client.is_time_available(
        datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30)
    )

    assert disponivel is True


async def test_is_time_available_false_quando_ha_evento_do_sistema_na_janela():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(
            structured_content={
                "count": 1,
                "events": [
                    {
                        "id": "evt1",
                        "summary": "[Sistema] Visita — Maria",
                        "description": "Origem: Agendamento Sistema\n[origem:sistema]",
                    }
                ],
            }
        )
    )
    client = _client(session)

    disponivel = await client.is_time_available(
        datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30)
    )

    assert disponivel is False


async def test_is_time_available_sem_chave_count_falha_fechado():
    # Achado 4 da revisão final (Fase 4A): se o schema real do MCP divergir
    # do assumido (ex.: campo renomeado), não pode silenciosamente tratar
    # como "sem eventos" — arriscaria criar um evento em cima de outro já
    # existente (double-booking). Deve falhar fechado.
    session = _FakeMCPSession(result=_FakeCallToolResult(structured_content={"outro_campo": []}))
    client = _client(session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.is_time_available(datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30))


async def test_is_time_available_structured_content_none_falha_fechado():
    session = _FakeMCPSession(result=_FakeCallToolResult(structured_content=None))
    client = _client(session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.is_time_available(datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30))


async def test_create_event_retorna_id_e_link_do_evento():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(
            structured_content={
                "calendar_id": "primary",
                "event": {"id": "evt1", "html_link": "https://calendar.google.com/evt1"},
                "message": "Created 'Visita — Maria' starting 2026-09-24T10:00:00.",
            }
        )
    )
    client = _client(session)

    event_id, link = await client.create_event(
        summary="Visita — Maria",
        start=datetime(2026, 9, 24, 10, 0),
        end=datetime(2026, 9, 24, 10, 30),
        attendee_email="maria@example.com",
        attendee_name="Maria",
    )

    assert event_id == "evt1"
    assert link == "https://calendar.google.com/evt1"
    nome_tool, argumentos = session.calls[0]
    assert nome_tool == "create_event"
    assert argumentos["calendar_id"] == "primary"
    assert argumentos["start_time"] == "2026-09-24T10:00:00"
    assert argumentos["end_time"] == "2026-09-24T10:30:00"
    assert argumentos["attendee_emails"] == ["maria@example.com"]
    # Garante inclusão do prefixo [Sistema] no summary e marcador na descrição
    assert argumentos["summary"] == "[Sistema] Visita — Maria"
    assert "Maria" in argumentos["description"]
    assert "[origem:sistema]" in argumentos["description"]


async def test_create_event_nao_duplica_prefixo_se_ja_existir():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(
            structured_content={
                "calendar_id": "primary",
                "event": {"id": "evt1", "html_link": "https://calendar.google.com/evt1"},
            }
        )
    )
    client = _client(session)

    await client.create_event(
        summary="[Sistema] Visita — Maria",
        start=datetime(2026, 9, 24, 10, 0),
        end=datetime(2026, 9, 24, 10, 30),
        attendee_email="maria@example.com",
        attendee_name="Maria",
    )

    _, argumentos = session.calls[0]
    assert argumentos["summary"] == "[Sistema] Visita — Maria"


async def test_create_event_sem_chave_event_retorna_id_e_link_vazios():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"calendar_id": "primary", "message": "ok"})
    )
    client = _client(session)

    event_id, link = await client.create_event(
        summary="Visita",
        start=datetime(2026, 9, 24, 10, 0),
        end=datetime(2026, 9, 24, 10, 30),
        attendee_email="a@b.com",
        attendee_name="A",
    )

    assert event_id == ""
    assert link == ""


async def test_delete_event_chama_tool_delete_event_com_sucesso():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(
            structured_content={"calendar_id": "primary", "message": "deleted"}
        )
    )
    client = _client(session)

    sucesso = await client.delete_event("evt1")

    assert sucesso is True
    assert len(session.calls) == 1
    nome_tool, argumentos = session.calls[0]
    assert nome_tool == "delete_event"
    assert argumentos["calendar_id"] == "primary"
    assert argumentos["event_id"] == "evt1"


async def test_delete_event_quando_tool_falha_com_not_found_retorna_false():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(is_error=True, content=["Event not found: evt404"])
    )
    client = _client(session)

    sucesso = await client.delete_event("evt404")

    assert sucesso is False


async def test_list_events_retorna_apenas_eventos_do_sistema():
    mock_events = [
        {
            "id": "evt1",
            "summary": "[Sistema] Visita — Maria",
            "description": "[origem:sistema]",
            "start": "2026-09-24T10:00:00Z",
        },
        {
            "id": "evt2",
            "summary": "Reunião de Diretoria",
            "description": "Orçamento anual",
            "start": "2026-09-24T11:00:00Z",
        },
        {
            "id": "evt3",
            "summary": "Visita — João",
            "description": "Visitante: João\nOrigem: Agendamento Sistema\n[origem:sistema]",
            "start": "2026-09-24T14:00:00Z",
        },
    ]
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"count": 3, "events": mock_events})
    )
    client = _client(session)

    eventos = await client.list_events(
        time_min=datetime(2026, 9, 24, 8, 0),
        time_max=datetime(2026, 9, 24, 18, 0),
    )

    # Apenas evt1 e evt3 devem ser retornados (evt2 é de outro assunto)
    assert len(eventos) == 2
    assert [e["id"] for e in eventos] == ["evt1", "evt3"]
    nome_tool, argumentos = session.calls[0]
    assert nome_tool == "find_events"
    assert argumentos["calendar_id"] == "primary"
    assert argumentos["time_min"] == "2026-09-24T08:00:00"
    assert argumentos["time_max"] == "2026-09-24T18:00:00"


async def test_call_tool_com_is_error_vira_connection_error():
    session = _FakeMCPSession(result=_FakeCallToolResult(is_error=True, content=["deu erro"]))
    client = _client(session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.is_time_available(datetime(2026, 9, 24, 10, 0), datetime(2026, 9, 24, 10, 30))


async def test_call_tool_excecao_de_transporte_vira_connection_error():
    session = _FakeMCPSession(exception=RuntimeError("conexão recusada"))
    client = _client(session)

    with pytest.raises(GoogleCalendarConnectionError):
        await client.create_event(
            summary="Visita",
            start=datetime(2026, 9, 24, 10, 0),
            end=datetime(2026, 9, 24, 10, 30),
            attendee_email="a@b.com",
            attendee_name="A",
        )
