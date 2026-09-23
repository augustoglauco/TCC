from contextlib import asynccontextmanager
from datetime import datetime

import pytest

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


async def test_is_time_available_true_quando_nao_ha_eventos():
    session = _FakeMCPSession(result=_FakeCallToolResult(structured_content={"count": 0}))
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


async def test_is_time_available_false_quando_ha_evento_na_janela():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"count": 1, "events": [{"id": "evt1"}]})
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


async def test_create_event_retorna_link_do_evento():
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
    assert argumentos["calendar_id"] == "primary"
    assert argumentos["start_time"] == "2026-09-24T10:00:00"
    assert argumentos["end_time"] == "2026-09-24T10:30:00"
    assert argumentos["attendee_emails"] == ["maria@example.com"]
    # A tool não aceita nome de exibição por convidado — vai na descrição.
    assert "Maria" in argumentos["description"]


async def test_create_event_sem_chave_event_retorna_link_vazio():
    session = _FakeMCPSession(
        result=_FakeCallToolResult(structured_content={"calendar_id": "primary", "message": "ok"})
    )
    client = _client(session)

    link = await client.create_event(
        summary="Visita",
        start=datetime(2026, 9, 24, 10, 0),
        end=datetime(2026, 9, 24, 10, 30),
        attendee_email="a@b.com",
        attendee_name="A",
    )

    assert link == ""


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
