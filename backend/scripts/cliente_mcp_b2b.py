"""Cliente de teste do MCP B2B (R12, Fase 5): faz o que a IA de um fornecedor
faria — conecta com a chave do parceiro, lista as ferramentas e pede uma
cotação. Serve para testar de fora da rede local (ex.: notebook no 4G) se o
caminho DuckDNS → Caddy (HTTPS) → servidor está de pé e a chave é aceita.

Uso (de qualquer máquina com Python e o pacote `mcp>=2.0`):

    python cliente_mcp_b2b.py --url https://augustoglauco.duckdns.org:8443/mcp \\
        --chave <chave-do-parceiro>

Também é usado pela suíte `mcp_b2b` de `scripts/teste_local.py`
(`verificar_mcp_b2b`). Ver docs/TESTE_LOCAL.md e docs/ARCHITECTURE.md §6.
"""

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass, field

import httpx2
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

_FERRAMENTAS_ESPERADAS = {"validar_compatibilidade", "consultar_frete", "cotar", "reservar_pedido"}


@dataclass
class ResultadoMcp:
    ok: bool
    etapas: list[str] = field(default_factory=list)
    erro: str | None = None
    cotacao: dict | None = None


async def status_sem_sessao(url: str, chave: str | None, timeout_s: float = 15.0) -> int:
    """Um POST `initialize` cru e devolve só o status HTTP — para conferir o
    `401` sem chave/chave errada sem depender do cliente MCP."""
    corpo = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "teste-local", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    if chave is not None:
        headers["Authorization"] = f"Bearer {chave}"
    async with httpx2.AsyncClient(timeout=timeout_s) as cliente:
        resposta = await cliente.post(url, json=corpo, headers=headers)
        return resposta.status_code


async def verificar_mcp_b2b(
    url: str, chave: str, produto_id: int = 1, quantidade: int = 2
) -> ResultadoMcp:
    """Sessão MCP completa com a chave: `initialize`, `tools/list` (as 4
    ferramentas) e `tools/call cotar`. Não chama `reservar_pedido`: ela cria
    pedido e baixa estoque de verdade."""
    resultado = ResultadoMcp(ok=False)
    try:
        # Confere a chave antes da sessão: com chave recusada o cliente MCP
        # só diz "Server returned an error response", pouco útil no relatório.
        status = await status_sem_sessao(url, chave)
        if status == 401:
            resultado.erro = "chave recusada pelo servidor (HTTP 401)"
            return resultado
        async with create_mcp_http_client(headers={"Authorization": f"Bearer {chave}"}) as http:
            async with streamable_http_client(url, http_client=http) as (leitura, escrita):
                async with ClientSession(leitura, escrita) as sessao:
                    inicio = await sessao.initialize()
                    resultado.etapas.append(f"initialize ok ({inicio.server_info.name})")
                    ferramentas = {f.name for f in (await sessao.list_tools()).tools}
                    faltando = _FERRAMENTAS_ESPERADAS - ferramentas
                    if faltando:
                        resultado.erro = f"ferramentas ausentes: {sorted(faltando)}"
                        return resultado
                    resultado.etapas.append(f"tools/list ok ({len(ferramentas)} ferramentas)")
                    cotacao = await sessao.call_tool(
                        "cotar", {"itens": [{"produto_id": produto_id, "quantidade": quantidade}]}
                    )
                    if cotacao.is_error:
                        resultado.erro = f"cotar devolveu erro: {_texto(cotacao)}"
                        return resultado
                    resultado.cotacao = cotacao.structured_content
                    resultado.etapas.append("tools/call cotar ok")
    except BaseException as exc:  # noqa: BLE001 — o SDK agrupa erros em ExceptionGroup
        resultado.erro = _descrever_erro(exc)
        return resultado
    resultado.ok = True
    return resultado


def _texto(resultado) -> str:
    return " ".join(getattr(item, "text", "") for item in resultado.content)


def _descrever_erro(exc: BaseException) -> str:
    # O cliente MCP embrulha a falha real (conexão recusada, 401, TLS) em
    # ExceptionGroup; mostra a mais interna, que é a que explica o problema.
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return f"{type(exc).__name__}: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--url", required=True, help="ex.: https://seu-dominio:8443/mcp")
    parser.add_argument("--chave", required=True, help="chave do parceiro (MCP_B2B_PARTNER_KEYS)")
    args = parser.parse_args()

    try:
        status = asyncio.run(status_sem_sessao(args.url, None))
    except httpx2.HTTPError as exc:
        # Servidor/Caddy fora do ar, porta fechada no roteador, DNS ou TLS.
        print(f"❌ Não conectou em {args.url}: {_descrever_erro(exc)}")
        return 1
    print(f"Sem chave: HTTP {status} {'✅' if status == 401 else '❌ (esperado 401)'}")
    resultado = asyncio.run(verificar_mcp_b2b(args.url, args.chave))
    for etapa in resultado.etapas:
        print(f"Com chave: {etapa} ✅")
    if resultado.cotacao is not None:
        print(json.dumps(resultado.cotacao, ensure_ascii=False, indent=2))
    if not resultado.ok:
        print(f"Com chave: ❌ {resultado.erro}")
    return 0 if resultado.ok and status == 401 else 1


if __name__ == "__main__":
    sys.exit(main())
