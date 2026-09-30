from contextlib import asynccontextmanager
import pytest
from src.client import B2BMCPClient, B2BAuthError, B2BMCPError


class _FakeCallToolResult:
    def __init__(self, structured_content=None, content=None, is_error=False):
        self.structured_content = structured_content or {}
        self.content = content or []
        self.is_error = is_error


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


@pytest.mark.asyncio
async def test_testar_conexao_sucesso():
    session = _FakeMCPSession()
    client = B2BMCPClient("http://fake/mcp", "chave_valida", session_factory=_fake_factory(session))
    info = await client.testar_conexao()
    assert info["ok"] is True
    assert info["servidor"] == "mcp-b2b-corporativo"
    assert "cotar" in info["ferramentas"]


@pytest.mark.asyncio
async def test_testar_conexao_chave_invalida_lanca_b2b_auth_error():
    session = _FakeMCPSession(is_401=True)
    client = B2BMCPClient("http://fake/mcp", "chave_invalida", session_factory=_fake_factory(session))
    with pytest.raises(B2BAuthError):
        await client.testar_conexao()


@pytest.mark.asyncio
async def test_cotar_chama_tool_correta():
    mock_cotacao = {
        "itens": [{"produto_id": 1, "quantidade": 2, "subtotal": 100.0}],
        "total_geral": 100.0,
    }
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_cotacao))
    client = B2BMCPClient("http://fake/mcp", "tok", session_factory=_fake_factory(session))

    resultado = await client.cotar([{"produto_id": 1, "quantidade": 2}])
    assert resultado["total_geral"] == 100.0
    assert len(session.calls) == 1
    assert session.calls[0][0] == "cotar"


@pytest.mark.asyncio
async def test_consultar_frete_chama_tool_correta():
    mock_frete = {"cep_destino": "01310100", "valor_total": 45.0, "prazo_dias_uteis": 3}
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_frete))
    client = B2BMCPClient("http://fake/mcp", "tok", session_factory=_fake_factory(session))

    resultado = await client.consultar_frete("01310-100", [{"produto_id": 1, "quantidade": 1}])
    assert resultado["valor_total"] == 45.0
    assert session.calls[0][0] == "consultar_frete"


@pytest.mark.asyncio
async def test_validar_compatibilidade_chama_tool():
    mock_comp = {"compativeis": True, "justificativa": "Produtos 100% compativeis"}
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_comp))
    client = B2BMCPClient("http://fake/mcp", "tok", session_factory=_fake_factory(session))

    resultado = await client.validar_compatibilidade(1, 2)
    assert resultado["compativeis"] is True
    assert session.calls[0][0] == "validar_compatibilidade"


@pytest.mark.asyncio
async def test_reservar_pedido_chama_tool():
    mock_ped = {"pedido_id": 123, "status": "confirmado", "total": 250.0}
    session = _FakeMCPSession(tool_result=_FakeCallToolResult(structured_content=mock_ped))
    client = B2BMCPClient("http://fake/mcp", "tok", session_factory=_fake_factory(session))

    resultado = await client.reservar_pedido([{"produto_id": 1, "quantidade": 2}], "01310-100", "EXT-99")
    assert resultado["pedido_id"] == 123
    assert session.calls[0][0] == "reservar_pedido"
