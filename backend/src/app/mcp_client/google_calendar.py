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

import httpx


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
