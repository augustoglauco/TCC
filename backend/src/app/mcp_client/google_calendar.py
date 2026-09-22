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
