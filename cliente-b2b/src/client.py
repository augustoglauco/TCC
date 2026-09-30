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
                raise B2BAuthError("Chave do parceiro recusada pelo servidor MCP (HTTP 401)") from exc
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
        payload: dict[str, Any] = {"itens": itens, "cep_entrega": cep_entrega}
        if identificador_externo:
            payload["identificador_externo_parceiro"] = identificador_externo
        return await self._call_tool("reservar_pedido", payload)
