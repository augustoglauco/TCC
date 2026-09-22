import httpx
import pytest

from scripts.authorize_google_calendar import (
    montar_url_autorizacao,
    trocar_codigo_por_refresh_token,
)


def test_montar_url_autorizacao_inclui_client_id_e_offline():
    url = montar_url_autorizacao("meu-client-id")

    assert "client_id=meu-client-id" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url


def test_trocar_codigo_por_refresh_token_devolve_o_token():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"refresh_token": "novo-refresh-token"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    token = trocar_codigo_por_refresh_token("cid", "csecret", "codigo-de-autorizacao", client)

    assert token == "novo-refresh-token"


def test_trocar_codigo_por_refresh_token_sem_refresh_token_na_resposta_falha():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"access_token": "sem-refresh-aqui"})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(SystemExit):
        trocar_codigo_por_refresh_token("cid", "csecret", "codigo", client)
