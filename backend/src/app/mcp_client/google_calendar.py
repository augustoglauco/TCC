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
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Protocol

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client


class GoogleCalendarConnectionError(Exception):
    """Falha de rede/protocolo ao falar com o MCP do Google Calendar, ou a
    tool retornou erro (ex.: `calendar-mcp-server` sem token válido — rodar
    `calendar-mcp-server auth` resolve)."""


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


class GoogleCalendarMCPClient:
    def __init__(
        self,
        mcp_server_url: str,
        calendar_id: str,
        session_factory=None,
    ) -> None:
        self._mcp_server_url = mcp_server_url
        self._calendar_id = calendar_id
        self._session_factory = session_factory or self._default_session_factory

    def _default_session_factory(self):
        @asynccontextmanager
        async def factory():
            async with create_mcp_http_client() as http_client:
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
        return resultado["count"] == 0

    async def create_event(
        self,
        summary: str,
        start: datetime,
        end: datetime,
        attendee_email: str,
        attendee_name: str,
        description: str = "",
    ) -> str:
        # A tool `create_event` deste servidor só aceita e-mails em
        # `attendee_emails` (sem nome de exibição por convidado) — o nome do
        # visitante vai para a descrição do evento para não se perder.
        descricao_completa = f"Visitante: {attendee_name}\n{description}".strip()
        resultado = await self._call_tool(
            "create_event",
            {
                "calendar_id": self._calendar_id,
                "summary": summary,
                "description": descricao_completa,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "attendee_emails": [attendee_email],
                "send_notifications": True,
            },
        )
        evento = resultado.get("event") or {}
        return evento.get("html_link", "")
