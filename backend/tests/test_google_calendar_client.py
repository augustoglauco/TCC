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


import httpx

from app.mcp_client.google_calendar import GoogleCalendarMCPClient


def _mock_transport(json_response: dict, status_code: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_response)

    return httpx.MockTransport(handler)


def _client(tmp_path, transport: httpx.MockTransport) -> GoogleCalendarMCPClient:
    credentials_path = tmp_path / "credentials.json"
    credentials_path.write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csecret"}}))
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"refresh_token": "rtoken"}))

    return GoogleCalendarMCPClient(
        credentials_path=str(credentials_path),
        token_path=str(token_path),
        calendar_id="primary",
        token_http_client=httpx.AsyncClient(transport=transport),
    )


async def test_get_access_token_troca_refresh_token_por_access_token(tmp_path):
    client = _client(tmp_path, _mock_transport({"access_token": "novo-token", "expires_in": 3600}))

    token = await client._get_access_token()

    assert token == "novo-token"


async def test_get_access_token_reaproveita_token_em_cache(tmp_path):
    chamadas = []

    def handler(request: httpx.Request) -> httpx.Response:
        chamadas.append(request)
        return httpx.Response(200, json={"access_token": "token-1", "expires_in": 3600})

    client = _client(tmp_path, httpx.MockTransport(handler))

    primeiro = await client._get_access_token()
    segundo = await client._get_access_token()

    assert primeiro == segundo == "token-1"
    assert len(chamadas) == 1  # segunda chamada não bateu na rede — usou o cache


async def test_get_access_token_renova_quando_expirado(tmp_path):
    respostas = [
        {"access_token": "token-1", "expires_in": -10},  # já "expirado" na criação
        {"access_token": "token-2", "expires_in": 3600},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=respostas.pop(0))

    client = _client(tmp_path, httpx.MockTransport(handler))

    primeiro = await client._get_access_token()
    segundo = await client._get_access_token()

    assert primeiro == "token-1"
    assert segundo == "token-2"


async def test_get_access_token_erro_http_vira_auth_error(tmp_path):
    client = _client(tmp_path, _mock_transport({"error": "invalid_grant"}, status_code=400))

    with pytest.raises(GoogleCalendarAuthError):
        await client._get_access_token()


async def test_get_access_token_resposta_sem_access_token_vira_auth_error(tmp_path):
    client = _client(tmp_path, _mock_transport({"expires_in": 3600}))

    with pytest.raises(GoogleCalendarAuthError):
        await client._get_access_token()
