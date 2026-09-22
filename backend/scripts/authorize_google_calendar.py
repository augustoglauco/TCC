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
