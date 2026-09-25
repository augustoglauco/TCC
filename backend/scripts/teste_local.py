"""Roteiro de teste local — roda na máquina do desenvolvedor e gera um
relatório único para devolver ao agente que escreveu o código.

Fluxo (ver docs/TESTE_LOCAL.md):
    1. `git pull` do branch com a mudança;
    2. subir a aplicação normalmente (goup.md) — backend na 8000, logando
       em /tmp/tcc-backend.log;
    3. `cd backend && .venv/bin/python scripts/teste_local.py --suite <nome>`;
    4. enviar o arquivo gerado em `testes_locais/` (colar o conteúdo ou
       commitar/pushar no mesmo branch).

Cada suíte tem duas partes:
    - checks automáticos (ruff + pytest) — pulados com `--sem-pytest`;
    - cenários de chat reais contra o backend no ar, capturando a resposta
      SSE (texto + evento `done`) e as linhas de log do backend geradas
      por aquela conversa. Cada cenário tem um "esperado" em texto livre; o
      veredito automático só aparece quando dá para decidir pelo log (ex.:
      etapa em que a consulta de vendas parou) — o resto é para o humano e
      o agente lerem.

# MVP: roteiro de apoio ao teste manual, não uma suíte de avaliação — a
# avaliação experimental do TCC continua em `eval/` (docs/EVALUATION.md).
"""

import argparse
import json
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
SAIDA_DIR = REPO_DIR / "testes_locais"

# Eventos de log do backend que interessam ao relatório — o resto (acesso
# HTTP, httpx, etc.) só polui.
_EVENTOS_DE_LOG = {
    "router_decision",
    "vendas_catalogo_consulta",
    "vendas_catalogo_consulta_falhou",
    "rag_indisponivel",
    "chat_dependencia_indisponivel",
}


@dataclass
class Cenario:
    nome: str
    mensagens: list[str]
    esperado: str
    # Valor esperado de `resultado` no log `vendas_catalogo_consulta` da
    # ÚLTIMA mensagem do cenário: str (um valor), tupla (qualquer um deles)
    # ou "nenhum" (o log não deve aparecer, ex.: domínio fora de vendas).
    # None = sem veredito automático.
    resultado_vendas: str | tuple[str, ...] | None = None
    # Trechos que devem aparecer no bloco injetado no prompt (campo `bloco`).
    bloco_contem: list[str] = field(default_factory=list)
    bloco_nao_contem: list[str] = field(default_factory=list)


# Dados semeados pelas migrações 0003/0008/0009: 5 produtos, cada um com
# 17 unidades em estoque (12 CD-SP + 5 CD-RJ), desconto de 5% a partir de 5
# unidades e 10% a partir de 10; compatibilidades QTA-100↔GD-15,
# QTA-100↔GD-30 e Cabine↔GD-30.
SUITES: dict[str, list[Cenario]] = {
    "vendas": [
        Cenario(
            nome="V1 — produto sem quantidade (só estoque)",
            mensagens=["Quanto custa o gerador GD-15? Tem em estoque?"],
            esperado="Bloco com o GD-15 e estoque 17; sem linha de cotação.",
            resultado_vendas="ok",
            bloco_contem=["GD-15", "17 unidade(s)"],
            bloco_nao_contem=["Cotação"],
        ),
        Cenario(
            nome="V2 — cotação abaixo da faixa de desconto",
            mensagens=["Quero cotação de 2 geradores GD-15"],
            esperado="Cotação para 2 unidades SEM texto de desconto (0%).",
            resultado_vendas="ok",
            bloco_contem=["Cotação para 2 unidade(s)"],
            bloco_nao_contem=["desconto"],
        ),
        Cenario(
            nome="V3 — cotação com desconto por volume (10%)",
            mensagens=["Preciso de 10 unidades do gerador GD-30, qual o valor total?"],
            esperado="Cotação para 10 unidades com 10.00% de desconto.",
            resultado_vendas="ok",
            bloco_contem=["GD-30", "Cotação para 10 unidade(s)", "10.00% de desconto"],
        ),
        Cenario(
            nome="V4 — compatibilidade que existe",
            mensagens=["O quadro de transferência QTA-100 é compatível com o gerador GD-30?"],
            esperado="Bloco com 'Compatível com ...: sim'.",
            resultado_vendas="ok",
            bloco_contem=[": sim"],
        ),
        Cenario(
            nome="V5 — compatibilidade que não existe",
            mensagens=["A cabine de insonorização serve no gerador GD-60?"],
            esperado="Bloco com 'Compatível com ...: não'.",
            resultado_vendas="ok",
            bloco_contem=[": não"],
        ),
        Cenario(
            nome="V6 — produto que não existe no catálogo",
            mensagens=["Vocês vendem painel solar fotovoltaico?"],
            esperado="Nenhum bloco do catálogo; resposta só com RAG/playbook.",
            resultado_vendas=("sem_candidatos", "llm_sem_produto"),
        ),
        Cenario(
            nome="V7 — domínio de suporte não consulta o catálogo",
            mensagens=["Meu gerador GD-15 não liga depois da chuva, o que eu faço?"],
            esperado="Domínio suporte; nenhum log vendas_catalogo_consulta.",
            resultado_vendas="nenhum",
        ),
        Cenario(
            nome="V8 — quantidade em mensagem seguinte (exploratório)",
            mensagens=["Quero comprar um gerador GD-15", "E se eu levar 5 unidades?"],
            esperado=(
                "Exploratório: a busca de candidatos só olha a mensagem atual, "
                "então a 2ª mensagem provavelmente não acha produto. Registrar o "
                "que acontece — é insumo para decidir se vale melhorar."
            ),
        ),
    ],
}


def _rodar(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def _checks_automaticos() -> list[str]:
    linhas = ["## 1. Checks automáticos", ""]
    codigo, saida = _rodar([sys.executable, "-m", "ruff", "check", "src", "tests"])
    linhas.append(f"- `ruff check`: {'OK' if codigo == 0 else 'FALHOU'}")
    if codigo != 0:
        linhas += ["", "```", saida.strip()[-3000:], "```", ""]

    codigo, saida = _rodar([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"])
    resumo = next(
        (linha for linha in reversed(saida.splitlines()) if " in " in linha and "passed" in linha),
        saida.strip().splitlines()[-1] if saida.strip() else "(sem saída)",
    )
    linhas.append(f"- `pytest`: {'OK' if codigo == 0 else 'FALHOU'} — {resumo.strip()}")
    falhas = [linha for linha in saida.splitlines() if linha.startswith(("FAILED", "ERROR"))]
    if falhas:
        linhas += ["", "```", *falhas[:50], "```"]
    return [*linhas, ""]


def _ler_sse(resposta: httpx.Response) -> tuple[str | None, str, dict | None, str | None]:
    conversation_id = None
    texto: list[str] = []
    done = None
    erro = None
    evento = None
    for linha in resposta.iter_lines():
        if linha.startswith("event:"):
            evento = linha.split(":", 1)[1].strip()
        elif linha.startswith("data:"):
            dados = json.loads(linha.split(":", 1)[1].strip())
            if evento == "conversation":
                conversation_id = dados.get("conversation_id")
            elif evento == "token":
                texto.append(dados.get("text", ""))
            elif evento == "done":
                done = dados
            elif evento == "error":
                erro = dados.get("detail")
    return conversation_id, "".join(texto), done, erro


def _novas_linhas_de_log(log_path: Path, offset: int, conversation_id: str | None) -> list[dict]:
    if not log_path.exists():
        return []
    with log_path.open("r", encoding="utf-8", errors="replace") as arquivo:
        arquivo.seek(offset)
        conteudo = arquivo.read()
    registros = []
    for linha in conteudo.splitlines():
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if not isinstance(registro, dict) or registro.get("message") not in _EVENTOS_DE_LOG:
            continue
        cid = registro.get("conversation_id")
        if conversation_id and cid and cid != conversation_id:
            continue
        registros.append(registro)
    return registros


def _veredito(cenario: Cenario, logs: list[dict]) -> tuple[str, list[str]]:
    if cenario.resultado_vendas is None:
        return "—", []
    consultas = [r for r in logs if r.get("message") == "vendas_catalogo_consulta"]
    problemas = []
    if cenario.resultado_vendas == "nenhum":
        if consultas:
            problemas.append("log vendas_catalogo_consulta apareceu, mas não deveria")
    else:
        esperados = (
            cenario.resultado_vendas
            if isinstance(cenario.resultado_vendas, tuple)
            else (cenario.resultado_vendas,)
        )
        if not consultas:
            problemas.append(
                "nenhum log vendas_catalogo_consulta (domínio não foi vendas? "
                "log do backend não está em --log?)"
            )
        else:
            ultimo = consultas[-1]
            if ultimo.get("resultado") not in esperados:
                problemas.append(
                    f"resultado={ultimo.get('resultado')!r}, esperado {' ou '.join(esperados)}"
                )
            bloco = ultimo.get("bloco") or ""
            problemas += [f"bloco sem {t!r}" for t in cenario.bloco_contem if t not in bloco]
            problemas += [f"bloco com {t!r}" for t in cenario.bloco_nao_contem if t in bloco]
    return ("PASSOU" if not problemas else "FALHOU"), problemas


def _rodar_cenario(
    cliente: httpx.Client, base_url: str, log_path: Path, cenario: Cenario
) -> tuple[str, list[str]]:
    linhas = [f"### {cenario.nome}", "", f"**Esperado:** {cenario.esperado}", ""]
    # Cada cenário numa conversa nova (UUID próprio) para o histórico curto
    # do roteador não vazar de um cenário para o outro.
    conversation_id = str(uuid.uuid4())
    logs_ultima: list[dict] = []
    for indice, mensagem in enumerate(cenario.mensagens, start=1):
        offset = log_path.stat().st_size if log_path.exists() else 0
        inicio = time.perf_counter()
        try:
            with cliente.stream(
                "POST",
                f"{base_url}/api/chat/messages",
                json={"message": mensagem, "conversation_id": conversation_id},
            ) as resposta:
                resposta.raise_for_status()
                _, texto, done, erro = _ler_sse(resposta)
        except httpx.HTTPError as exc:
            texto, done, erro = "", None, f"{type(exc).__name__}: {exc}"
        duracao = time.perf_counter() - inicio
        time.sleep(0.3)  # dá tempo do handler de log gravar as últimas linhas
        logs = _novas_linhas_de_log(log_path, offset, conversation_id)
        logs_ultima = logs

        linhas.append(f"**Mensagem {indice}:** {mensagem}")
        linhas.append("")
        if erro:
            linhas.append(f"- ⚠️ erro: `{erro}`")
        if done:
            linhas.append(
                f"- domínio `{done.get('domain')}` · backend `{done.get('backend_used')}` · "
                f"motivo `{done.get('escalation_reason')}` · modelo `{done.get('model_name')}` · "
                f"rag_retrieval_ms `{done.get('rag_retrieval_ms')}` · total {duracao:.1f}s"
            )
        linhas += ["", "Resposta do assistente:", "", "```text", texto.strip() or "(vazia)", "```"]
        consultas = [r for r in logs if r.get("message") != "router_decision"]
        if consultas:
            linhas += ["", "Logs do backend (vendas/erros):", "", "```json"]
            for registro in consultas:
                resumo = {k: v for k, v in registro.items() if k not in {"level", "logger"}}
                linhas.append(json.dumps(resumo, ensure_ascii=False, indent=2))
            linhas.append("```")
        linhas.append("")

    veredito, problemas = _veredito(cenario, logs_ultima)
    linhas.append(f"**Veredito automático:** {veredito}")
    linhas += [f"- {problema}" for problema in problemas]
    linhas.append("")
    return veredito, linhas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--suite", choices=sorted(SUITES), required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--log", default="/tmp/tcc-backend.log", type=Path)
    parser.add_argument("--sem-pytest", action="store_true", help="pula ruff + pytest")
    parser.add_argument(
        "--so", help="roda só os cenários cujo nome começa com este prefixo (ex.: V3)"
    )
    args = parser.parse_args()

    commit = _rodar(["git", "rev-parse", "--short", "HEAD"])[1].strip()
    branch = _rodar(["git", "rev-parse", "--abbrev-ref", "HEAD"])[1].strip()
    agora = datetime.now()
    relatorio = [
        f"# Resultado do teste local — suíte `{args.suite}`",
        "",
        f"- Data: {agora:%Y-%m-%d %H:%M}",
        f"- Branch/commit: `{branch}` @ `{commit}`",
        f"- Backend: {args.base_url} · log: `{args.log}`",
        "",
    ]

    if not args.sem_pytest:
        print("Rodando ruff + pytest...", flush=True)
        relatorio += _checks_automaticos()

    relatorio += ["## 2. Cenários de chat", ""]
    placar: dict[str, int] = {}
    cenarios = [c for c in SUITES[args.suite] if not args.so or c.nome.startswith(args.so)]
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=5.0)) as cliente:
        try:
            cliente.get(f"{args.base_url}/docs").raise_for_status()
        except httpx.HTTPError as exc:
            relatorio += [f"⚠️ Backend inacessível em {args.base_url}: `{exc}`", ""]
            cenarios = []
        for cenario in cenarios:
            print(f"Cenário: {cenario.nome}", flush=True)
            veredito, linhas = _rodar_cenario(cliente, args.base_url, args.log, cenario)
            placar[veredito] = placar.get(veredito, 0) + 1
            relatorio += linhas

    relatorio[6:6] = [
        "Placar dos cenários: "
        + (", ".join(f"{k}: {v}" for k, v in sorted(placar.items())) or "nenhum rodou"),
        "",
    ]
    relatorio += [
        "## 3. Observações do testador",
        "",
        "<!-- Opcional: o que você viu no chat do navegador, algo estranho na resposta, etc. -->",
        "",
    ]

    if not args.log.exists():
        relatorio[4] += " ⚠️ (arquivo não encontrado — relatório sem logs do backend)"

    SAIDA_DIR.mkdir(exist_ok=True)
    saida = SAIDA_DIR / f"{agora:%Y%m%d-%H%M}-{args.suite}.md"
    saida.write_text("\n".join(relatorio), encoding="utf-8")
    print(f"\nRelatório gravado em: {saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
