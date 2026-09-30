from contextlib import asynccontextmanager
import json
import pytest
from src.client import B2BMCPClient, B2BAuthError, B2BMCPError


class _FakeCallToolResult:
    def __init__(self, structured_content=None, content=None, is_error=False):
        self.structured_content = structured_content or {}
        self.content = content or []
        self.is_error = is_error


class _FakeResourceContent:
    def __init__(self, texto: str):
        self.text = texto


class _FakeReadResourceResult:
    def __init__(self, contents=None):
        self.contents = contents or []


class _FakeServerInfo:
    name = "mcp-b2b-corporativo"
    version = "1.0.0"


class _FakeInitResult:
    server_info = _FakeServerInfo()


class _FakeToolInfo:
    def __init__(self, name):
        self.name = name


class _FakeListToolsResult:
    def __init__(self, tools):
        self.tools = [_FakeToolInfo(t) for t in tools]


class _FakeMCPSession:
    def __init__(self, tool_result=None, resource_result=None, is_401=False):
        self.tool_result = tool_result
        self.resource_result = resource_result
        self.is_401 = is_401
        self.calls: list[tuple[str, dict]] = []

    async def initialize(self):
        if self.is_401:
            raise RuntimeError("HTTP 401: Unauthorized")
        return _FakeInitResult()

    async def list_tools(self):
        return _FakeListToolsResult(["cotar", "consultar_frete", "validar_compatibilidade", "reservar_pedido"])

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return self.tool_result

    async def read_resource(self, uri):
        return self.resource_result


def _fake_factory(session: _FakeMCPSession):
    @asynccontextmanager
    async def factory():
        yield session
    return factory


def _fake_prober(session: _FakeMCPSession):
    async def prober(url, token, timeout_s):
        return 401 if session.is_401 else 200
    return prober


def _novo_cliente(session: _FakeMCPSession, url="http://fake/mcp", token="tok"):
    return B2BMCPClient(
        url, token, session_factory=_fake_factory(session), auth_prober=_fake_prober(session)
    )


@pytest.mark.asyncio
async def test_testar_conexao_sucesso():
    session = _FakeMCPSession()
    client = _novo_cliente(session, token="chave_valida")
    info = await client.testar_conexao()
    assert info["ok"] is True
    assert info["servidor"] == "mcp-b2b-corporativo"
    assert "cotar" in info["ferramentas"]


@pytest.mark.asyncio
async def test_testar_conexao_chave_invalida_lanca_b2b_auth_error():
    session = _FakeMCPSession(is_401=True)
    client = _novo_cliente(session, token="chave_invalida")
    with pytest.raises(B2BAuthError):
        await client.testar_conexao()


@pytest.mark.asyncio
async def test_cotar_chama_tool_correta():
    mock_cotacao = {
        "itens": [{"produto_id": 1, "quantidade": 2, "subtotal": 100.0}],
        "total_geral": 100.0,
    }
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_cotacao))
    client = _novo_cliente(session)

    resultado = await client.cotar([{"produto_id": 1, "quantidade": 2}])
    assert resultado["total_geral"] == 100.0
    assert len(session.calls) == 1
    assert session.calls[0][0] == "cotar"


@pytest.mark.asyncio
async def test_consultar_frete_chama_tool_correta():
    mock_frete = {"cep": "01310100", "peso_total_kg": 2.0, "custo_estimado": 45.0, "prazo_dias": 3}
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_frete))
    client = _novo_cliente(session)

    resultado = await client.consultar_frete("01310-100", [{"produto_id": 1, "quantidade": 1}])
    assert resultado["custo_estimado"] == 45.0
    assert session.calls[0][0] == "consultar_frete"
    assert session.calls[0][1]["cep"] == "01310-100"


@pytest.mark.asyncio
async def test_validar_compatibilidade_chama_tool():
    mock_comp = {"produto_id": 1, "produto_relacionado_id": 2, "compativel": True}
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_comp))
    client = _novo_cliente(session)

    resultado = await client.validar_compatibilidade(1, 2)
    assert resultado["compativel"] is True
    assert session.calls[0][0] == "validar_compatibilidade"
    assert session.calls[0][1] == {"produto_id": 1, "produto_relacionado_id": 2}


@pytest.mark.asyncio
async def test_reservar_pedido_chama_tool():
    mock_ped = {
        "id": "3f6a1c1a-0000-4000-8000-000000000000",
        "status": "reservado",
        "criado_em": "2026-09-30T00:00:00Z",
        "itens": [{"produto_id": 1, "quantidade": 2, "centro_distribuicao": "SP", "preco_unitario": 125.0}],
    }
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_ped))
    client = _novo_cliente(session)

    resultado = await client.reservar_pedido(
        [{"produto_id": 1, "quantidade": 2, "centro_distribuicao": "SP"}]
    )
    assert resultado["status"] == "reservado"
    assert session.calls[0][0] == "reservar_pedido"


@pytest.mark.asyncio
async def test_obter_catalogo_recurso():
    produtos = [{"id": 1, "nome": "Gerador X"}, {"id": 2, "nome": "Gerador Y"}]
    session = _FakeMCPSession(resource_result=_FakeReadResourceResult([_FakeResourceContent(json.dumps(produtos))]))
    client = _novo_cliente(session)

    resultado = await client.obter_catalogo()
    assert resultado == produtos


@pytest.mark.asyncio
async def test_obter_estoque_recurso():
    estoque = {"produto_id": 1, "centros": [{"centro_distribuicao": "SP", "quantidade": 10}]}
    session = _FakeMCPSession(resource_result=_FakeReadResourceResult([_FakeResourceContent(json.dumps(estoque))]))
    client = _novo_cliente(session)

    resultado = await client.obter_estoque(1)
    assert resultado == estoque


@pytest.mark.asyncio
async def test_pesquisar_manuais_recurso():
    busca = {"resultados": [{"content": "trecho relevante", "source": "manual.pdf", "score": 0.9, "collection": "c1"}]}
    session = _FakeMCPSession(resource_result=_FakeReadResourceResult([_FakeResourceContent(json.dumps(busca))]))
    client = _novo_cliente(session)

    resultado = await client.pesquisar_manuais("vendas", "cabo de rede")
    assert resultado == busca["resultados"]
