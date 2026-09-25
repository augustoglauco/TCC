"""Autenticação do MCP B2B por chave de parceiro (R12, Fase 5) — decisão de
2026-09-25 em docs/ARCHITECTURE.md §6. Os testes HTTP passam pelo app
Starlette real do SDK (middleware de autenticação + proteção de Host), não
só pelo verificador isolado."""

import logging
from contextlib import asynccontextmanager

import httpx
import pytest
from qdrant_client import AsyncQdrantClient

from app.db.engine import create_db_engine, create_session_factory
from app.db.models import Base
from app.mcp_server.auth import (
    ChaveParceiroVerifier,
    ChavesParceirosInvalidasError,
    carregar_chaves_parceiros,
    configuracao_auth,
    preparar_autenticacao,
    seguranca_de_transporte,
)
from app.mcp_server.b2b import create_b2b_mcp_server
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient

_URL_PUBLICA = "https://parceiro.example:8443/mcp"
_CHAVE_DEMO = "chave-fornecedor-demo-0123456789"
_CHAVE_B = "chave-fornecedor-b-abcdefghijklmn"
_CALL_COMPATIBILIDADE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "validar_compatibilidade",
        "arguments": {"produto_id": 1, "produto_relacionado_id": 2},
    },
}
_HEADERS_MCP = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
}


# --- Leitura de MCP_B2B_PARTNER_KEYS -----------------------------------------


def test_carregar_chaves_parceiros_le_varias_chaves_com_nome():
    chaves = carregar_chaves_parceiros(f"fornecedor-demo:{_CHAVE_DEMO}, fornecedor-b:{_CHAVE_B}")

    assert chaves == {_CHAVE_DEMO: "fornecedor-demo", _CHAVE_B: "fornecedor-b"}


def test_carregar_chaves_parceiros_vazio_devolve_dicionario_vazio():
    assert carregar_chaves_parceiros("") == {}
    assert carregar_chaves_parceiros(" , ") == {}


@pytest.mark.parametrize(
    "valor",
    [
        "fornecedor-demo",  # sem ":"
        f":{_CHAVE_DEMO}",  # sem nome
        "fornecedor-demo:",  # sem chave
        "fornecedor-demo:curta",  # chave com menos de 16 caracteres
        f"a:{_CHAVE_DEMO},a:{_CHAVE_B}",  # nome repetido
        f"a:{_CHAVE_DEMO},b:{_CHAVE_DEMO}",  # chave repetida
    ],
)
def test_carregar_chaves_parceiros_recusa_configuracao_invalida(valor):
    with pytest.raises(ChavesParceirosInvalidasError):
        carregar_chaves_parceiros(valor)


# --- Verificador ---------------------------------------------------------------


async def test_verificador_identifica_o_parceiro_pela_chave():
    verificador = ChaveParceiroVerifier({_CHAVE_DEMO: "fornecedor-demo", _CHAVE_B: "fornecedor-b"})

    token = await verificador.verify_token(_CHAVE_B)

    assert token is not None
    assert token.client_id == "fornecedor-b"


async def test_verificador_recusa_chave_desconhecida():
    verificador = ChaveParceiroVerifier({_CHAVE_DEMO: "fornecedor-demo"})

    assert await verificador.verify_token("chave-que-nao-existe-0000") is None
    assert await verificador.verify_token(_CHAVE_DEMO[:-1]) is None


# --- Pelo HTTP real do SDK -----------------------------------------------------


# Gerenciador de contexto, não fixture: o `pytest-asyncio` abre e fecha
# fixtures assíncronas em tasks diferentes, e o gerenciador de sessões do SDK
# (anyio) exige sair na mesma task em que entrou.
@asynccontextmanager
async def _cliente_http():
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    server = create_b2b_mcp_server(
        create_session_factory(engine),
        QdrantRAGClient(host="unused", port=0, client=AsyncQdrantClient(location=":memory:")),
        EmbedderRegistry(),
        token_verifier=ChaveParceiroVerifier({_CHAVE_DEMO: "fornecedor-demo"}),
        auth=configuracao_auth(_URL_PUBLICA),
    )
    # Sem sessão (stateless) e com resposta JSON: cada POST é independente,
    # o que deixa o teste focado na autenticação, não no handshake do MCP.
    app = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        transport_security=seguranca_de_transporte(_URL_PUBLICA),
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://parceiro.example:8443"
        ) as cliente:
            yield cliente
    await engine.dispose()


async def test_sem_chave_recebe_401():
    async with _cliente_http() as cliente_http:
        resposta = await cliente_http.post("/mcp", json=_CALL_COMPATIBILIDADE, headers=_HEADERS_MCP)

        assert resposta.status_code == 401
        assert resposta.headers["www-authenticate"].startswith("Bearer")


async def test_chave_errada_recebe_401():
    async with _cliente_http() as cliente_http:
        resposta = await cliente_http.post(
            "/mcp",
            json=_CALL_COMPATIBILIDADE,
            headers={**_HEADERS_MCP, "Authorization": "Bearer chave-que-nao-existe-0000"},
        )

        assert resposta.status_code == 401


async def test_chave_certa_chama_a_ferramenta_e_loga_o_parceiro(caplog):
    with caplog.at_level(logging.INFO, logger="app.mcp_server.b2b"):
        async with _cliente_http() as cliente_http:
            resposta = await cliente_http.post(
                "/mcp",
                json=_CALL_COMPATIBILIDADE,
                headers={**_HEADERS_MCP, "Authorization": f"Bearer {_CHAVE_DEMO}"},
            )

    assert resposta.status_code == 200
    # Catálogo vazio: a ferramenta roda e devolve erro de negócio (produto
    # inexistente) — o que importa aqui é ter passado pela autenticação.
    assert "não encontrado" in resposta.json()["result"]["content"][0]["text"]
    [registro] = [r for r in caplog.records if r.getMessage() == "mcp_b2b_ferramenta"]
    assert registro.router["parceiro"] == "fornecedor-demo"
    assert registro.router["ferramenta"] == "validar_compatibilidade"
    assert registro.router["resultado"] == "erro"


async def test_host_fora_da_url_publica_e_recusado():
    async with _cliente_http() as cliente_http:
        # Proteção do SDK contra DNS rebinding continua ligada: só o host da
        # URL pública (e localhost) passa, mesmo com chave válida.
        resposta = await cliente_http.post(
            "/mcp",
            json=_CALL_COMPATIBILIDADE,
            headers={
                **_HEADERS_MCP,
                "Authorization": f"Bearer {_CHAVE_DEMO}",
                "Host": "outro-dominio.example",
            },
        )

        assert resposta.status_code == 421


# --- Falha fechada e URL pública ----------------------------------------------


def test_preparar_autenticacao_sem_chave_nao_deixa_subir():
    with pytest.raises(ChavesParceirosInvalidasError, match="não sobe"):
        preparar_autenticacao("", "", "127.0.0.1", 8100)


def test_preparar_autenticacao_libera_o_host_da_url_publica():
    autenticacao = preparar_autenticacao(
        f"fornecedor-demo:{_CHAVE_DEMO}", _URL_PUBLICA, "127.0.0.1", 8100
    )

    assert autenticacao.parceiros == ["fornecedor-demo"]
    assert str(autenticacao.auth.resource_server_url) == _URL_PUBLICA
    assert "parceiro.example:8443" in autenticacao.seguranca.allowed_hosts
    assert "127.0.0.1:*" in autenticacao.seguranca.allowed_hosts


def test_preparar_autenticacao_sem_url_publica_fica_so_local():
    autenticacao = preparar_autenticacao(f"fornecedor-demo:{_CHAVE_DEMO}", "", "127.0.0.1", 8100)

    assert str(autenticacao.auth.resource_server_url) == "http://127.0.0.1:8100/mcp"
    assert autenticacao.seguranca.allowed_hosts == ["127.0.0.1:*", "localhost:*", "[::1]:*"]
