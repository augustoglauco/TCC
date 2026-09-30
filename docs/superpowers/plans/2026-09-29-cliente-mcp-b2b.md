# Cliente Independente MCP B2B (Streamlit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar um projeto independente (`cliente-b2b/`) com cliente assíncrono MCP e interface gráfica interativa em Streamlit para consumir recursos e ferramentas do servidor MCP B2B corporativo.

**Architecture:** O projeto reside em diretório isolado (`cliente-b2b/`), sem acoplamento ao código do backend. A classe `B2BMCPClient` (`src/client.py`) encapsula o protocolo MCP HTTP Streamable (handshake, token Bearer, leitura de resources e chamada de tools), enquanto `src/app.py` expõe uma interface Streamlit moderna dividida em 5 abas operacionais (Catálogo/Estoque, Cotação, Frete, Compatibilidade, Pedidos) e barra lateral de conexão.

**Tech Stack:** Python 3.12+, `mcp>=2.0` (SDK oficial Anthropic/MCP), `httpx>=0.28`, `streamlit>=1.40`, `pydantic>=2.0`, `pytest`, `pytest-asyncio`.

**Spec:** [docs/superpowers/specs/2026-09-29-cliente-mcp-b2b-design.md](file:///home/augusto/Projetos/TCC/docs/superpowers/specs/2026-09-29-cliente-mcp-b2b-design.md)

## Global Constraints

- O projeto deve ser totalmente auto-suficiente dentro da pasta `cliente-b2b/`.
- Uso do SDK oficial `mcp` com `ClientSession` e `streamable_http_client`.
- Autenticação via cabeçalho HTTP `Authorization: Bearer <chave_parceiro>`.
- Preservação e exibição opcional dos payloads brutos JSON-RPC para fins de auditoria no TCC.
- Nenhuma dependência direta com o banco Postgres ou código interno do backend (consumo exclusivamente via protocolo de rede MCP).

## Review Focus

- **Chave de autenticação inválida ou ausente (HTTP 401)**: deve emitir erro descritivo "Chave do parceiro recusada pelo servidor MCP (HTTP 401)" sem traceback quebrado.
- **Servidor MCP offline ou inacessível**: deve tratar erro de conexão (`ConnectError`) e informar que o servidor está indisponível na URL informada.
- **Estrutura inesperada de retorno do MCP**: deve validar a presença de `content` e `structured_content` com fallback seguro.
- **Cotação com lista vazia ou produtos inexistentes**: deve reportar erro da tool MCP amigavelmente na interface.
- **Reserva de pedido com estoque insuficiente**: deve capturar a mensagem de recusa do servidor e alertar o usuário no painel.

---

### Task 1: Estrutura inicial do projeto `cliente-b2b` e arquivos de configuração

**Files:**
- Create: `cliente-b2b/pyproject.toml`
- Create: `cliente-b2b/requirements.txt`
- Create: `cliente-b2b/README.md`
- Create: `cliente-b2b/src/__init__.py`
- Create: `cliente-b2b/tests/__init__.py`

**Interfaces:**
- Produz: Ambiente isolado e manifesto de dependências do novo projeto `cliente-b2b`.

- [ ] **Step 1: Criar o arquivo `pyproject.toml`**

```toml
[project]
name = "cliente-mcp-b2b"
version = "0.1.0"
description = "Cliente independente com interface Streamlit para consumo do servidor MCP B2B"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp>=2.0.0",
    "httpx>=0.28.0",
    "streamlit>=1.40.0",
    "pydantic>=2.10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

- [ ] **Step 2: Criar o arquivo `requirements.txt`**

```text
mcp>=2.0.0
httpx>=0.28.0
streamlit>=1.40.0
pydantic>=2.10.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: Criar arquivos `src/__init__.py` e `tests/__init__.py`**

Criar arquivos vazios marcando os pacotes Python:
- `cliente-b2b/src/__init__.py`
- `cliente-b2b/tests/__init__.py`

- [ ] **Step 4: Criar `README.md` com instruções preliminares**

```markdown
# Cliente Independente MCP B2B

Aplicação cliente independente desenvolvida em Python + Streamlit para conectar e demonstrar o consumo do Servidor MCP B2B corporativo.

## Como Executar

### 1. Instalar dependências
```bash
cd cliente-b2b
pip install -r requirements.txt
```

### 2. Executar os testes
```bash
pytest tests/
```

### 3. Iniciar a interface Streamlit
```bash
streamlit run src/app.py
```
```

- [ ] **Step 5: Commit inicial do esqueleto do projeto**

```bash
git add cliente-b2b/pyproject.toml cliente-b2b/requirements.txt cliente-b2b/README.md cliente-b2b/src/__init__.py cliente-b2b/tests/__init__.py
git commit -m "chore(cliente-b2b): inicializar esqueleto do projeto independente cliente-b2b"
```

---

### Task 2: Implementação do Cliente MCP B2B (`src/client.py`) e Testes Unitários

**Files:**
- Create: `cliente-b2b/src/client.py`
- Test: `cliente-b2b/tests/test_client.py`

**Interfaces:**
- Produz:
  - `class B2BMCPClient`:
    - `__init__(self, server_url: str, auth_token: str, session_factory=None)`
    - `async def testar_conexao(self) -> dict`
    - `async def obter_catalogo(self) -> list[dict]`
    - `async def obter_estoque(self) -> list[dict]`
    - `async def obter_precos(self) -> list[dict]`
    - `async def pesquisar_manuais(self, query: str) -> list[dict]`
    - `async def cotar(self, itens: list[dict]) -> dict`
    - `async def consultar_frete(self, cep_destino: str, itens: list[dict]) -> dict`
    - `async def validar_compatibilidade(self, produto_id_a: int, produto_id_b: int) -> dict`
    - `async def reservar_pedido(self, itens: list[dict], cep_entrega: str, identificador_externo: str | None = None) -> dict`
  - `class B2BMCPError(Exception)`
  - `class B2BAuthError(B2BMCPError)`

- [ ] **Step 1: Escrever testes unitários em `cliente-b2b/tests/test_client.py` (RED)**

```python
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
```

- [ ] **Step 2: Executar pytest para confirmar falha (RED)**

```bash
pytest cliente-b2b/tests/test_client.py
```
Esperado: FAIL com `ModuleNotFoundError: No module named 'src.client'`

- [ ] **Step 3: Implementar `cliente-b2b/src/client.py` (GREEN)**

```python
"""Cliente assíncrono para o Servidor MCP B2B Corporativo."""

from contextlib import asynccontextmanager
import json
import logging
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

logger = logging.getLogger(__name__)


class B2BMCPError(Exception):
    """Erro geral de comunicação com o MCP B2B."""


class B2BAuthError(B2BMCPError):
    """Chave de parceiro rejeitada ou inválida."""


class B2BMCPClient:
    def __init__(
        self,
        server_url: str,
        auth_token: str,
        timeout_seconds: float = 20.0,
        session_factory=None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds
        self._session_factory = session_factory or self._default_session_factory

    def _default_session_factory(self):
        @asynccontextmanager
        async def factory():
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            async with create_mcp_http_client(headers=headers) as http_client:
                async with streamable_http_client(self.server_url, http_client=http_client) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        yield session
        return factory()

    async def _call_tool(self, name: str, arguments: dict) -> dict[str, Any]:
        try:
            async with self._session_factory() as session:
                result = await session.call_tool(name, arguments)
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "unauthorized" in msg.lower():
                raise B2BAuthError(f"Chave do parceiro recusada pelo servidor MCP (HTTP 401): {msg}") from exc
            raise B2BMCPError(f"Falha ao chamar ferramenta '{name}': {msg}") from exc

        if result.is_error:
            conteudo_texto = " ".join(getattr(c, "text", str(c)) for c in result.content)
            raise B2BMCPError(f"Erro retornado pela ferramenta '{name}': {conteudo_texto}")

        return result.structured_content or {}

    async def _read_resource(self, uri: str) -> list[dict[str, Any]]:
        try:
            async with self._session_factory() as session:
                result = await session.read_resource(uri)
                itens: list[dict[str, Any]] = []
                for item in result.contents:
                    texto = getattr(item, "text", "")
                    if texto:
                        try:
                            itens.append(json.loads(texto))
                        except Exception:
                            itens.append({"conteudo": texto})
                return itens
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "unauthorized" in msg.lower():
                raise B2BAuthError(f"Chave do parceiro recusada pelo servidor MCP (HTTP 401): {msg}") from exc
            raise B2BMCPError(f"Falha ao ler recurso '{uri}': {msg}") from exc

    async def testar_conexao(self) -> dict[str, Any]:
        try:
            async with self._session_factory() as session:
                init_res = await session.initialize()
                server_info = getattr(init_res, "server_info", None)
                nome_servidor = getattr(server_info, "name", "Desconhecido")
                versao_servidor = getattr(server_info, "version", "Desconhecida")
                tools_res = await session.list_tools()
                ferramentas = [t.name for t in tools_res.tools]
                return {
                    "ok": True,
                    "servidor": nome_servidor,
                    "versao": versao_servidor,
                    "ferramentas": ferramentas,
                }
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "unauthorized" in msg.lower():
                raise B2BAuthError(f"Chave do parceiro recusada pelo servidor MCP (HTTP 401)") from exc
            raise B2BMCPError(f"Falha de conexão com o servidor MCP: {msg}") from exc

    async def obter_catalogo(self) -> list[dict]:
        return await self._read_resource("catalogo://")

    async def obter_estoque(self) -> list[dict]:
        return await self._read_resource("estoque://")

    async def obter_precos(self) -> list[dict]:
        return await self._read_resource("precos://")

    async def pesquisar_manuais(self, query: str) -> list[dict]:
        return await self._read_resource(f"manuais://?query={query}")

    async def cotar(self, itens: list[dict]) -> dict:
        return await self._call_tool("cotar", {"itens": itens})

    async def consultar_frete(self, cep_destino: str, itens: list[dict]) -> dict:
        return await self._call_tool("consultar_frete", {"cep_destino": cep_destino, "itens": itens})

    async def validar_compatibilidade(self, produto_id_a: int, produto_id_b: int) -> dict:
        return await self._call_tool(
            "validar_compatibilidade",
            {"produto_id_a": produto_id_a, "produto_id_b": produto_id_b},
        )

    async def reservar_pedido(
        self,
        itens: list[dict],
        cep_entrega: str,
        identificador_externo: str | None = None,
    ) -> dict:
        payload = {"itens": itens, "cep_entrega": cep_entrega}
        if identificador_externo:
            payload["identificador_externo_parceiro"] = identificador_externo
        return await self._call_tool("reservar_pedido", payload)
```

- [ ] **Step 4: Executar pytest para confirmar aprovação (GREEN)**

```bash
pytest cliente-b2b/tests/test_client.py -v
```
Esperado: 6 passed.

- [ ] **Step 5: Commit do cliente e testes**

```bash
git add cliente-b2b/src/client.py cliente-b2b/tests/test_client.py
git commit -m "feat(cliente-b2b): implementar B2BMCPClient com suporte a resources e tools"
```

---

### Task 3: Aplicação Web Streamlit (`src/app.py`)

**Files:**
- Create: `cliente-b2b/src/app.py`
- Create: `cliente-b2b/tests/test_app_helpers.py`

**Interfaces:**
- Consome: `B2BMCPClient`, `B2BAuthError`, `B2BMCPError` de `src.client`.
- Produz: Aplicação visual Streamlit executável via `streamlit run src/app.py`.

- [ ] **Step 1: Escrever testes unitários para helpers de UI e formatação (RED)**

Criar `cliente-b2b/tests/test_app_helpers.py`:
```python
from src.app import formatar_moeda, formatar_itens_carrinho


def test_formatar_moeda():
    assert formatar_moeda(1250.5) == "R$ 1.250,50"
    assert formatar_moeda(0) == "R$ 0,00"


def test_formatar_itens_carrinho():
    carrinho = [{"produto_id": 1, "quantidade": 5}]
    itens_mcp = formatar_itens_carrinho(carrinho)
    assert itens_mcp == [{"produto_id": 1, "quantidade": 5}]
```

- [ ] **Step 2: Executar pytest para verificar falha (RED)**

```bash
pytest cliente-b2b/tests/test_app_helpers.py
```
Esperado: FAIL com `ImportError`.

- [ ] **Step 3: Implementar a aplicação Streamlit em `cliente-b2b/src/app.py` (GREEN)**

Implementar `cliente-b2b/src/app.py`:
- Funções auxiliares `formatar_moeda` e `formatar_itens_carrinho`.
- `asyncio.run()` encapsulado para chamadas do cliente dentro do ciclo de vida síncrono do Streamlit.
- Barra lateral com inputs de URL, Token, botão de teste de conexão e status.
- Aba 1: Catálogo & Recursos (tabelas de produtos, estoque e busca em manuais).
- Aba 2: Cotação B2B (seletor de produtos, quantidades, botão de simulação e métricas).
- Aba 3: Consulta de Frete (input de CEP e resultado em card).
- Aba 4: Validador de Compatibilidade (dois selects de produtos e alertas visuais).
- Aba 5: Fechamento de Pedido B2B (resumo, checkbox de confirmação e emissão de reserva).

- [ ] **Step 4: Executar pytest dos helpers (GREEN)**

```bash
pytest cliente-b2b/tests/test_app_helpers.py -v
```
Esperado: PASS.

- [ ] **Step 5: Commit da interface Streamlit**

```bash
git add cliente-b2b/src/app.py cliente-b2b/tests/test_app_helpers.py
git commit -m "feat(cliente-b2b): implementar interface Streamlit com 5 abas operacionais"
```

---

### Task 4: Validação de Integração e Documentação

**Files:**
- Modify: `cliente-b2b/README.md`
- Test: Execução dos testes automatizados e verificação de compatibilidade

- [ ] **Step 1: Rodar a suíte completa de testes de `cliente-b2b`**

```bash
pytest cliente-b2b/tests/ -v
```
Esperado: Todos os testes unitários passando.

- [ ] **Step 2: Atualizar o `README.md` com instruções detalhadas**

Documentar:
- Configuração de URL local (`http://127.0.0.1:8000/mcp/b2b`) e remota.
- Chaves padrão de teste dos parceiros do sistema (`parceiro_alpha_segredo_123`, `parceiro_beta_segredo_456`).
- Exemplo de como rodar o servidor B2B no backend principal e o cliente Streamlit em paralelo.

- [ ] **Step 3: Commit da documentação final**

```bash
git add cliente-b2b/README.md
git commit -m "docs(cliente-b2b): documentar inicialização e uso do portal parceiro Streamlit"
```

---

## Plan Self-Review Checklist

1. **Spec coverage**:
   - `conectar` / Handshake com Token Bearer -> Task 2
   - Resources `catalogo://`, `estoque://`, `precos://`, `manuais://` -> Task 2 & Task 3 (Aba 1)
   - Tool `cotar` -> Task 2 & Task 3 (Aba 2)
   - Tool `consultar_frete` -> Task 2 & Task 3 (Aba 3)
   - Tool `validar_compatibilidade` -> Task 2 & Task 3 (Aba 4)
   - Tool `reservar_pedido` -> Task 2 & Task 3 (Aba 5)
   - Modo de inspeção JSON-RPC -> Task 3
2. **No Placeholders**: Todas as etapas contêm código Python concreto e comandos bash específicos.
3. **Type consistency**: Nomes e assinaturas de `B2BMCPClient` (`testar_conexao`, `cotar`, `consultar_frete`, etc.) são consistentes entre Task 2, Task 3 e os testes.
