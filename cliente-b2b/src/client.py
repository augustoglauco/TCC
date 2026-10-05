"""Cliente assíncrono para o Servidor MCP B2B Corporativo."""

from contextlib import asynccontextmanager
import json
import logging
from typing import Any, Awaitable, Callable

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

logger = logging.getLogger(__name__)


class B2BMCPError(Exception):
    """Erro geral de comunicação com o MCP B2B."""


class B2BAuthError(B2BMCPError):
    """Chave de parceiro rejeitada ou inválida."""


async def _probe_status_http(url: str, token: str, timeout_s: float) -> int:
    """POST `initialize` cru (sem sessão MCP) só para ler o status HTTP —
    mesma técnica de `backend/scripts/cliente_mcp_b2b.py:status_sem_sessao`.
    Necessário porque o cliente MCP (`ClientSession.initialize`) embrulha um
    401 num `MCPError` JSON-RPC genérico ("Server returned an error
    response"), sem o código HTTP, então checar a mensagem da exceção do SDK
    nunca detecta a chave recusada — confirmado em teste real contra o
    servidor (ver ROADMAP.md, Fase 5)."""
    corpo = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "cliente-b2b-streamlit", "version": "0.1.0"},
        },
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as http:
        resposta = await http.post(url, json=corpo, headers=headers)
        return resposta.status_code


class B2BMCPClient:
    def __init__(
        self,
        server_url: str,
        auth_token: str,
        timeout_seconds: float = 20.0,
        session_factory=None,
        auth_prober: Callable[[str, str, float], Awaitable[int]] | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout_seconds = timeout_seconds
        self._session_factory = session_factory or self._default_session_factory
        self._auth_prober = auth_prober or _probe_status_http

    async def _verificar_autenticacao(self) -> None:
        if not self.auth_token:
            raise B2BAuthError("Chave do parceiro não informada.")
        try:
            status = await self._auth_prober(self.server_url, self.auth_token, self.timeout_seconds)
        except Exception as exc:
            raise B2BMCPError(f"Falha de conexão com o servidor MCP: {exc}") from exc
        if status == 401:
            raise B2BAuthError("Chave do parceiro recusada pelo servidor MCP (HTTP 401).")

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
        await self._verificar_autenticacao()
        try:
            async with self._session_factory() as session:
                result = await session.call_tool(name, arguments)
        except Exception as exc:
            raise B2BMCPError(f"Falha ao chamar ferramenta '{name}': {exc}") from exc

        if result.is_error:
            conteudo_texto = " ".join(getattr(c, "text", str(c)) for c in result.content)
            raise B2BMCPError(f"Erro retornado pela ferramenta '{name}': {conteudo_texto}")

        return result.structured_content or {}

    async def _read_resource(self, uri: str) -> list[dict[str, Any]]:
        # Os recursos do servidor devolvem ora uma lista JSON (ex.:
        # catalogo://produtos), ora um único objeto JSON (ex.:
        # catalogo://produtos/{id}, manuais://busca/{domain}) — achata os
        # dois formatos numa lista única para um único ponto de parsing.
        await self._verificar_autenticacao()
        try:
            async with self._session_factory() as session:
                result = await session.read_resource(uri)
                itens: list[dict[str, Any]] = []
                for item in result.contents:
                    texto = getattr(item, "text", "")
                    if texto:
                        try:
                            conteudo = json.loads(texto)
                        except Exception:
                            itens.append({"conteudo": texto})
                            continue
                        if isinstance(conteudo, list):
                            itens.extend(conteudo)
                        else:
                            itens.append(conteudo)
                return itens
        except Exception as exc:
            raise B2BMCPError(f"Falha ao ler recurso '{uri}': {exc}") from exc

    async def testar_conexao(self) -> dict[str, Any]:
        await self._verificar_autenticacao()
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
            raise B2BMCPError(f"Falha de conexão com o servidor MCP: {exc}") from exc

    async def obter_catalogo(self, categoria: str | None = None) -> list[dict]:
        uri = "catalogo://produtos"
        if categoria:
            uri += f"?categoria={categoria}"
        return await self._read_resource(uri)

    async def obter_produto_detalhe(self, produto_id: int) -> dict:
        itens = await self._read_resource(f"catalogo://produtos/{produto_id}")
        return itens[0] if itens else {}

    async def obter_estoque(self, produto_id: int) -> dict:
        itens = await self._read_resource(f"estoque://produtos/{produto_id}")
        return itens[0] if itens else {}

    async def obter_precos(self, produto_id: int) -> dict:
        itens = await self._read_resource(f"precos://produtos/{produto_id}")
        return itens[0] if itens else {}

    async def pesquisar_manuais(self, domain: str, query: str) -> list[dict]:
        itens = await self._read_resource(f"manuais://busca/{domain}?query={query}")
        if itens and "resultados" in itens[0]:
            return itens[0]["resultados"]
        return itens

    async def cotar(self, itens: list[dict]) -> dict:
        return await self._call_tool("cotar", {"itens": itens})

    async def consultar_frete(self, cep: str, itens: list[dict]) -> dict:
        return await self._call_tool("consultar_frete", {"cep": cep, "itens": itens})

    async def validar_compatibilidade(self, produto_id: int, produto_relacionado_id: int) -> dict:
        return await self._call_tool(
            "validar_compatibilidade",
            {"produto_id": produto_id, "produto_relacionado_id": produto_relacionado_id},
        )

    async def reservar_pedido(self, itens: list[dict]) -> dict:
        """`itens`: `[{"produto_id": int, "quantidade": int, "centro_distribuicao": str}]`."""
        return await self._call_tool("reservar_pedido", {"itens": itens})

    async def converter_reserva_venda(
        self,
        pedido_id: str,
        comprovante_base64_ou_texto: str,
        nome_arquivo: str = "comprovante.txt",
    ) -> dict:
        """Converte uma reserva pendente em venda concluída através de comprovante financeiro."""
        return await self._call_tool(
            "converter_reserva_venda",
            {
                "pedido_id": pedido_id,
                "comprovante_base64_ou_texto": comprovante_base64_ou_texto,
                "nome_arquivo": nome_arquivo,
            },
        )
