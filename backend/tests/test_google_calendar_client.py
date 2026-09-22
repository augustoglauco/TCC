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
