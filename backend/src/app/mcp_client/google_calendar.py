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
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

_CALENDAR_MCP_URL = "https://calendarmcp.googleapis.com/mcp/v1"


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
            f"Não foi possível ler o arquivo de credenciais do Google Calendar ({path}): {exc}"
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
        @asynccontextmanager
        async def factory():
            headers = {"Authorization": f"Bearer {access_token}"}
            async with create_mcp_http_client(headers=headers) as http_client:
                async with streamable_http_client(_CALENDAR_MCP_URL, http_client=http_client) as (
                    read_stream,
                    write_stream,
                ):
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
        # Falha FECHADA (revisão final, achado 4): se a resposta não tiver a
        # chave "events" — schema inesperado do endpoint real, ainda não
        # confirmado contra a nota acima — não assume "lista vazia" (que
        # tornaria qualquer horário "disponível" e arriscaria um
        # double-booking real). Trata como falha de MCP, mesmo tratamento de
        # `GoogleCalendarConnectionError` já usado pelo resto do cliente.
        if "events" not in resultado:
            raise GoogleCalendarConnectionError(
                "Resposta inesperada da tool 'list_events' do MCP do Google "
                f"Calendar: não contém a chave 'events' (recebido: {resultado!r})."
            )
        eventos = resultado["events"]
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
