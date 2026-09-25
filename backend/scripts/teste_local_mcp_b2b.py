"""Suíte `mcp_b2b` do teste local (`scripts/teste_local.py --suite mcp_b2b`):
confere a autenticação por chave de parceiro e o caminho HTTPS público do
MCP B2B — decisão de 2026-09-25 em docs/ARCHITECTURE.md §6.

Lê `MCP_B2B_PARTNER_KEYS`/`MCP_B2B_PUBLIC_URL`/`MCP_B2B_PORT` do `backend/.env`
(via `app.config`). A chave em si nunca entra no relatório, só o nome do
parceiro.
"""

import asyncio
import json
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from cliente_mcp_b2b import status_sem_sessao, verificar_mcp_b2b

from app.config import get_settings
from app.mcp_server.auth import ChavesParceirosInvalidasError, carregar_chaves_parceiros

LOG_MCP_B2B = Path("/tmp/tcc-mcp-b2b.log")


@dataclass
class Verificacao:
    nome: str
    esperado: str
    veredito: str  # "PASSOU" | "FALHOU" | "—" (não deu para verificar daqui)
    obtido: str


def rodar_verificacoes() -> tuple[dict[str, int], list[str]]:
    settings = get_settings()
    url_local = f"http://127.0.0.1:{settings.mcp_b2b_port}/mcp"
    url_publica = settings.mcp_b2b_public_url.strip()
    verificacoes: list[Verificacao] = []

    try:
        chaves = carregar_chaves_parceiros(settings.mcp_b2b_partner_keys)
    except ChavesParceirosInvalidasError as exc:
        chaves, erro_chaves = {}, str(exc)
    else:
        erro_chaves = "MCP_B2B_PARTNER_KEYS vazio no backend/.env" if not chaves else ""
    if not chaves:
        verificacoes.append(
            Verificacao(
                "M0 — chaves configuradas", "pelo menos uma chave válida", "FALHOU", erro_chaves
            )
        )
        return _formatar(verificacoes, url_local, url_publica, parceiro=None)
    chave, parceiro = next(iter(chaves.items()))

    print("MCP B2B: acesso local sem chave / chave errada", flush=True)
    verificacoes.append(_status("M1 — local, sem chave", url_local, None))
    verificacoes.append(_status("M2 — local, chave errada", url_local, "chave-errada-" + "x" * 20))

    print("MCP B2B: sessão MCP completa com a chave", flush=True)
    offset = LOG_MCP_B2B.stat().st_size if LOG_MCP_B2B.exists() else 0
    verificacoes.append(_sessao("M3 — local, chave certa", url_local, chave, parceiro, offset))

    verificacoes.append(_nao_escuta_na_rede(settings.mcp_b2b_port))

    if url_publica:
        print("MCP B2B: Caddy local e URL pública", flush=True)
        verificacoes.append(_caddy_local(url_publica))
        verificacoes.append(_publica_de_dentro(url_publica))
    else:
        verificacoes.append(
            Verificacao(
                "M5/M6 — URL pública",
                "MCP_B2B_PUBLIC_URL configurada",
                "—",
                "MCP_B2B_PUBLIC_URL vazio no backend/.env: só o acesso local foi testado.",
            )
        )
    return _formatar(verificacoes, url_local, url_publica, parceiro)


def _status(nome: str, url: str, chave: str | None) -> Verificacao:
    try:
        status = asyncio.run(status_sem_sessao(url, chave))
    except Exception as exc:  # noqa: BLE001 — qualquer falha de conexão vira resultado
        return Verificacao(nome, "HTTP 401", "FALHOU", f"não conectou: {type(exc).__name__}: {exc}")
    return Verificacao(nome, "HTTP 401", "PASSOU" if status == 401 else "FALHOU", f"HTTP {status}")


def _sessao(nome: str, url: str, chave: str, parceiro: str, offset: int) -> Verificacao:
    esperado = (
        "initialize + tools/list (4 ferramentas) + cotar ok; log mcp_b2b_ferramenta com o "
        f"parceiro `{parceiro}`"
    )
    resultado = asyncio.run(verificar_mcp_b2b(url, chave))
    if not resultado.ok:
        etapas = "; ".join(resultado.etapas) or "nenhuma etapa"
        return Verificacao(nome, esperado, "FALHOU", f"{etapas} — {resultado.erro}")
    registros = _logs_ferramenta(offset)
    obtido = "; ".join(resultado.etapas) + f"; cotação: {json.dumps(resultado.cotacao)}"
    if not any(r.get("parceiro") == parceiro and r.get("ferramenta") == "cotar" for r in registros):
        return Verificacao(
            nome,
            esperado,
            "FALHOU",
            obtido + f" — nenhum log mcp_b2b_ferramenta de `{parceiro}` em {LOG_MCP_B2B}",
        )
    return Verificacao(nome, esperado, "PASSOU", obtido + f"; log com parceiro `{parceiro}` ✔")


def _logs_ferramenta(offset: int) -> list[dict]:
    if not LOG_MCP_B2B.exists():
        return []
    with LOG_MCP_B2B.open(encoding="utf-8", errors="replace") as arquivo:
        arquivo.seek(offset)
        linhas = arquivo.read().splitlines()
    registros = []
    for linha in linhas:
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict) and registro.get("message") == "mcp_b2b_ferramenta":
            registros.append(registro)
    return registros


def _nao_escuta_na_rede(porta: int) -> Verificacao:
    """O servidor deve aceitar só 127.0.0.1: de fora, o único caminho é o
    Caddy (HTTPS). Tenta conectar pelo IP da máquina na rede local."""
    nome = f"M4 — porta {porta} fechada para a rede"
    esperado = "conexão recusada pelo IP da LAN"
    ip = _ip_na_rede()
    if ip is None:
        return Verificacao(nome, esperado, "—", "não achei o IP desta máquina na rede")
    try:
        with socket.create_connection((ip, porta), timeout=3):
            pass
    except OSError:
        return Verificacao(nome, esperado, "PASSOU", f"{ip}:{porta} recusou a conexão")
    return Verificacao(
        nome, esperado, "FALHOU", f"{ip}:{porta} aceitou conexão — MCP_B2B_HOST não é 127.0.0.1?"
    )


def _ip_na_rede() -> str | None:
    # UDP "connect" não envia pacote: só pergunta ao sistema qual interface
    # sairia para a internet, e daí o IP desta máquina na rede.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
    except OSError:
        return None
    return None if ip.startswith("127.") else ip


def _caddy_local(url_publica: str) -> Verificacao:
    """Fala com o Caddy desta máquina usando o domínio público (curl
    --resolve), sem depender do roteador: confere proxy + certificado."""
    nome = "M5 — Caddy local com o domínio público (HTTPS)"
    esperado = "HTTP 401 com certificado válido"
    partes = urlsplit(url_publica)
    host, porta = partes.hostname, partes.port or 443
    comando = [
        "curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10",
        "--resolve", f"{host}:{porta}:127.0.0.1",
        "-X", "POST", "-H", "Content-Type: application/json",
        "-H", "Accept: application/json, text/event-stream",
        "-d", '{"jsonrpc":"2.0","id":1,"method":"ping"}',
        url_publica,
    ]  # fmt: skip
    try:
        proc = subprocess.run(comando, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return Verificacao(nome, esperado, "FALHOU", f"curl falhou: {exc}")
    codigo = proc.stdout.strip()
    if proc.returncode != 0:
        return Verificacao(
            nome,
            esperado,
            "FALHOU",
            f"curl saiu com {proc.returncode}: {proc.stderr.strip()[:300]}",
        )
    return Verificacao(nome, esperado, "PASSOU" if codigo == "401" else "FALHOU", f"HTTP {codigo}")


def _publica_de_dentro(url_publica: str) -> Verificacao:
    nome = "M6 — URL pública a partir desta rede"
    esperado = "HTTP 401 (roteador + DuckDNS + Caddy)"
    try:
        status = asyncio.run(status_sem_sessao(url_publica, None, timeout_s=10))
    except Exception as exc:  # noqa: BLE001
        return Verificacao(
            nome,
            esperado,
            "—",
            f"não conectou de dentro da rede ({type(exc).__name__}). Normal em roteador sem "
            "NAT loopback: confirme de fora, com `cliente_mcp_b2b.py` num notebook no 4G "
            "(docs/TESTE_LOCAL.md).",
        )
    return Verificacao(nome, esperado, "PASSOU" if status == 401 else "FALHOU", f"HTTP {status}")


def _formatar(
    verificacoes: list[Verificacao], url_local: str, url_publica: str, parceiro: str | None
) -> tuple[dict[str, int], list[str]]:
    placar: dict[str, int] = {}
    linhas = [
        "## 2. Verificações do MCP B2B",
        "",
        f"- URL local: `{url_local}` · URL pública: `{url_publica or '(não configurada)'}`",
        f"- Parceiro usado no teste: `{parceiro or '—'}` (a chave não entra no relatório)",
        f"- Log do servidor: `{LOG_MCP_B2B}`",
        "",
    ]
    for v in verificacoes:
        placar[v.veredito] = placar.get(v.veredito, 0) + 1
        linhas += [
            f"### {v.nome}",
            "",
            f"**Esperado:** {v.esperado}",
            "",
            f"**Obtido:** {v.obtido}",
            "",
            f"**Veredito automático:** {v.veredito}",
            "",
        ]
    return placar, linhas
