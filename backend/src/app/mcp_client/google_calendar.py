"""Cliente MCP do Google Calendar (R11, Fase 4A) — consome um servidor MCP de
terceiro, self-hosted (`calendar-mcp-server`, pacote PyPI, código em
https://github.com/deciduus/calendar-mcp), via HTTP local — não mais o MCP
oficial do Google (`calendarmcp.googleapis.com`).

Decisão revista em docs/ARCHITECTURE.md §5 (2026-09-23): o MCP oficial do
Google está em Developer Preview e exige inscrição em programa fechado que
contas Gmail pessoais não conseguem (achado ao validar contra a API real —
toda chamada de tool retornava `isError: true` com essa mensagem explícita,
mesmo com token/escopo corretos). `calendar-mcp-server` roda como processo
local separado (`calendar-mcp-server serve --transport http`), gerencia sua
própria autenticação OAuth/token (`calendar-mcp-server auth`, usa as mesmas
credenciais OAuth "Desktop app" já criadas) — este cliente só fala MCP HTTP
local com ele, sem nenhum token management do lado do backend.

# MVP: uma só agenda da empresa (GOOGLE_CALENDAR_CALENDAR_ID), sem
reautenticação automática por visitante. Endpoint local sem autenticação
própria (mesmo padrão de Qdrant/Postgres neste protótipo — confiança de rede
local/docker, não exposto publicamente).

# MVP: disponibilidade (`is_time_available`) e listagem (`list_events`)
consideram só eventos marcados como criados pelo próprio sistema
(`is_system_event`, decisão de 2026-09-29, ver docs/ARCHITECTURE.md §5) — um
evento lançado manualmente direto no Google Calendar não bloqueia mais um
novo agendamento nem aparece no painel admin, podendo colidir na mesma
agenda com um evento do sistema.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Protocol

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

# Timeout padrão do SDK `mcp` para leitura (`create_mcp_http_client` sem
# `timeout`) é 300s — alto demais para um dependência de turno de chat.
# `GoogleCalendarMCPClient` sempre recebe um valor explícito
# (`Settings.calendar_mcp_timeout_s`); esta constante só cobre quem
# instancia a classe direto sem passar `timeout_s` (ex.: testes antigos).
DEFAULT_TIMEOUT_S = 15.0


class GoogleCalendarConnectionError(Exception):
    """Falha de rede/protocolo ao falar com o MCP do Google Calendar, ou a
    tool retornou erro (ex.: `calendar-mcp-server` sem token válido — rodar
    `calendar-mcp-server auth` resolve)."""


SYSTEM_TAG = "[origem:sistema]"
SYSTEM_SUMMARY_PREFIX = "[Sistema]"


def is_system_event(evento: dict[str, Any]) -> bool:
    """Verifica se o evento do Google Calendar pertence ao sistema.

    Identifica pela presença de '[Sistema]' no summary/título
    ou do marcador '[origem:sistema]' na descrição ou summary.
    """
    summary = str(evento.get("summary") or "")
    description = str(evento.get("description") or "")

    if SYSTEM_SUMMARY_PREFIX.lower() in summary.lower():
        return True
    if SYSTEM_TAG.lower() in summary.lower() or SYSTEM_TAG.lower() in description.lower():
        return True
    return False


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
    ) -> tuple[str, str]: ...

    async def delete_event(self, event_id: str) -> bool: ...

    async def list_events(self, time_min: datetime, time_max: datetime) -> list[dict]: ...


class GoogleCalendarMCPClient:
    def __init__(
        self,
        mcp_server_url: str,
        calendar_id: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        session_factory=None,
    ) -> None:
        self._mcp_server_url = mcp_server_url
        self._calendar_id = calendar_id
        self._timeout_s = timeout_s
        self._session_factory = session_factory or self._default_session_factory

    def _default_session_factory(self):
        @asynccontextmanager
        async def factory():
            # `create_mcp_http_client` (SDK `mcp`) usa internamente o pacote
            # `httpx2` (fork/sucessor do `httpx` adotado pelo SDK a partir da
            # versão 2.x) — passar um `httpx.Timeout` (pacote antigo) aqui
            # quebra silenciosamente dentro do `httpcore2`/`anyio` com um
            # `TypeError` encapsulado num `ExceptionGroup`, reportado só como
            # "unhandled errors in a TaskGroup".
            timeout = httpx2.Timeout(self._timeout_s)
            async with create_mcp_http_client(timeout=timeout) as http_client:
                async with streamable_http_client(
                    self._mcp_server_url, http_client=http_client
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        yield session

        return factory()

    async def _call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        try:
            async with self._session_factory() as session:
                result = await session.call_tool(name, arguments)
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
            "find_events",
            {
                "calendar_id": self._calendar_id,
                "time_min": start.isoformat(),
                "time_max": end.isoformat(),
            },
        )
        # Falha FECHADA (revisão final da Fase 4A, achado 4): se a resposta
        # não tiver a chave "count" — schema inesperado do servidor MCP —
        # não assume "lista vazia" (que tornaria qualquer horário
        # "disponível" e arriscaria um double-booking real). Trata como
        # falha de MCP, mesmo tratamento de `GoogleCalendarConnectionError`
        # já usado pelo resto do cliente.
        if "count" not in resultado:
            raise GoogleCalendarConnectionError(
                "Resposta inesperada da tool 'find_events' do MCP do Google "
                f"Calendar: não contém a chave 'count' (recebido: {resultado!r})."
            )

        events = resultado.get("events")
        if events is None and resultado["count"] > 0:
            return False

        system_events = [e for e in (events or []) if is_system_event(e)]
        return len(system_events) == 0

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> tuple[str, str]:
        # Formata o summary com prefixo do sistema caso ainda não possua
        clean_summary = summary.strip()
        if not clean_summary.lower().startswith(SYSTEM_SUMMARY_PREFIX.lower()):
            clean_summary = f"{SYSTEM_SUMMARY_PREFIX} {clean_summary}"

        # A tool `create_event` deste servidor só aceita e-mails em
        # `attendee_emails` (sem nome de exibição por convidado) — o nome do
        # visitante vai para a descrição do evento para não se perder.
        partes_descricao = [
            f"Visitante: {attendee_name}",
        ]
        if description.strip():
            partes_descricao.append(description.strip())
        partes_descricao.append(f"Origem: Agendamento Sistema\n{SYSTEM_TAG}")
        descricao_completa = "\n\n".join(partes_descricao).strip()

        resultado = await self._call_tool(
            "create_event",
            {
                "calendar_id": self._calendar_id,
                "summary": clean_summary,
                "description": descricao_completa,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "attendee_emails": [attendee_email],
                "send_notifications": True,
            },
        )
        evento = resultado.get("event") or {}
        return evento.get("id", ""), evento.get("html_link", "")

    async def delete_event(self, event_id: str) -> bool:
        try:
            await self._call_tool(
                "delete_event",
                {
                    "calendar_id": self._calendar_id,
                    "event_id": event_id,
                },
            )
            return True
        except GoogleCalendarConnectionError as exc:
            msg = str(exc).lower()
            if "not found" in msg or "404" in msg:
                return False
            raise

    async def list_events(self, time_min: datetime, time_max: datetime) -> list[dict]:
        resultado = await self._call_tool(
            "find_events",
            {
                "calendar_id": self._calendar_id,
                "time_min": time_min.isoformat(),
                "time_max": time_max.isoformat(),
            },
        )
        all_events = resultado.get("events", [])
        return [e for e in all_events if is_system_event(e)]
