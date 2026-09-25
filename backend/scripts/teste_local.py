"""Roteiro de teste local — roda na máquina do desenvolvedor e gera um
relatório único para devolver ao agente que escreveu o código.

Fluxo (ver docs/TESTE_LOCAL.md):
    1. `git pull` do branch com a mudança;
    2. subir a aplicação normalmente (goup.md) — backend na 8000, logando
       em /tmp/tcc-backend.log;
    3. `cd backend && .venv/bin/python scripts/teste_local.py` (roda a
       suíte `SUITE_ATUAL`; `--suite <nome>` escolhe outra);
    4. enviar o arquivo gerado em `testes_locais/`.

Na prática o desenvolvedor não chama este arquivo direto: `./testar.sh`,
na raiz do repo, faz os quatro passos (inclusive o push do relatório).

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
    "perfil_classificado",
    "resumo_atualizado",
    "resumo_falhou",
    "memoria_indisponivel",
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
    # Trechos que a RESPOSTA da última mensagem deve (ou não) conter — para
    # pegar o LLM ignorando o bloco do catálogo (ex.: citar outro produto).
    resposta_contem: list[str] = field(default_factory=list)
    resposta_nao_contem: list[str] = field(default_factory=list)
    # Pelo menos um destes trechos na resposta (sem diferenciar maiúsculas).
    resposta_contem_algum: list[str] = field(default_factory=list)
    # Memória da conversa (R9/R10, Fase 6):
    perfil_esperado: str | None = None  # `perfil_usuario` do último `done`
    historico_esperado: int | None = None  # mensagens em GET /conversations/{id}
    # Espera o resumo em segundo plano antes de mandar a ÚLTIMA mensagem.
    esperar_resumo: bool = False
    resumo_contem: list[str] = field(default_factory=list)


# Dados semeados pelas migrações 0003/0008/0009: 5 produtos, cada um com
# 17 unidades em estoque (12 CD-SP + 5 CD-RJ), desconto de 5% a partir de 5
# unidades e 10% a partir de 10; compatibilidades QTA-100↔GD-15,
# QTA-100↔GD-30 e Cabine↔GD-30.
# Suíte que `./testar.sh` (raiz do repo) roda quando nenhuma é passada — o
# agente troca este valor a cada entrega que precisa de validação local.
SUITE_ATUAL = "memoria"

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
            nome="V8 — quantidade em mensagem seguinte",
            mensagens=["Quero comprar um gerador GD-15", "E se eu levar 5 unidades?"],
            esperado=(
                "2ª mensagem: bloco com GD-15 e cotação de 5 unidades com 5% de "
                "desconto (R$ 118275.00), e a resposta fala do GD-15, não de outro "
                "gerador. No 1º teste (2026-09-25) o bloco estava certo, mas a "
                "resposta citou o GD-60 tirado do RAG."
            ),
            resultado_vendas="ok",
            bloco_contem=["GD-15", "Cotação para 5 unidade(s)", "5.00% de desconto"],
            resposta_contem=["GD-15"],
            resposta_nao_contem=["GD-60", "GD-30"],
        ),
        Cenario(
            nome="V9 — acompanhamento sem o produto na mensagem",
            mensagens=["Quero comprar um gerador GD-30", "E se eu levar 3 unidades?"],
            esperado=(
                "2ª mensagem: o produto vem do histórico (termos_historico no log). "
                "Bloco com GD-30 e cotação de 3 unidades sem desconto (R$ 127500.00); "
                "a resposta fala do GD-30. Antes da correção, '3 unidades' não "
                "achava produto nenhum."
            ),
            resultado_vendas="ok",
            bloco_contem=["GD-30", "Cotação para 3 unidade(s)", "127500.00"],
            bloco_nao_contem=["desconto aplicado"],
            resposta_contem=["GD-30"],
            resposta_nao_contem=["GD-15", "GD-60"],
        ),
    ],
    # Memória da conversa e classificação do usuário (R9/R10, Fase 6). Os
    # e-mails são os da base fictícia da migração 0011: Ana (3 compras
    # recentes), Bruno (1 compra), Carla (2 compras há mais de 12 meses).
    "memoria": [
        Cenario(
            nome="R1 — conversa gravada no Postgres",
            mensagens=["Quanto custa o gerador GD-30?", "E tem em estoque?"],
            esperado="4 mensagens gravadas (2 do cliente, 2 do assistente); perfil lead.",
            historico_esperado=4,
            perfil_esperado="lead",
        ),
        Cenario(
            nome="R2 — resumo automático usado na resposta",
            mensagens=[
                "Quero comprar o gerador GD-30",
                "Preciso de 3 unidades",
                "Vocês entregam em Campinas?",
                "Me lembra qual modelo e quantas unidades eu pedi?",
            ],
            esperado=(
                "Depois de 3 trocas o resumo é gerado em segundo plano (espera até 120 s) "
                "e cita o GD-30; a 4ª resposta lembra o modelo."
            ),
            esperar_resumo=True,
            resumo_contem=["30"],
            resposta_contem=["GD-30"],
        ),
        Cenario(
            nome="R3 — pós-venda sem e-mail: o assistente pede o e-mail",
            mensagens=["Meu gerador parou de funcionar depois da chuva, o que eu faço?"],
            esperado="Resposta pede o e-mail usado na compra; perfil não classificado.",
            resposta_contem_algum=["e-mail", "email"],
            perfil_esperado="nao_classificado",
        ),
        Cenario(
            nome="R4 — e-mail de cliente recorrente",
            mensagens=["Meu gerador GD-15 parou. Meu e-mail é ana.recorrente@example.com"],
            esperado="Perfil cliente (3 compras, a última há 30 dias).",
            perfil_esperado="cliente",
        ),
        Cenario(
            nome="R5 — e-mail de quem comprou uma vez",
            mensagens=["Preciso da nota fiscal. Meu e-mail é bruno.unico@example.com"],
            esperado="Perfil esporadico (uma única compra).",
            perfil_esperado="esporadico",
        ),
        Cenario(
            nome="R6 — e-mail de quem comprou há mais de um ano",
            mensagens=["Quero trocar uma peça, meu e-mail é carla.antiga@example.com"],
            esperado="Perfil esporadico (2 compras, a última há 500 dias).",
            perfil_esperado="esporadico",
        ),
        Cenario(
            nome="R7 — lead com e-mail sem cadastro",
            mensagens=[
                "Quero um orçamento de 2 geradores GD-15, meu e-mail é novo.lead@example.com"
            ],
            esperado="Perfil lead (intenção de compra, e-mail sem cadastro).",
            perfil_esperado="lead",
        ),
        Cenario(
            nome="R8 — sem sinais",
            mensagens=["Oi, bom dia!"],
            esperado="Perfil nao_classificado.",
            perfil_esperado="nao_classificado",
        ),
        Cenario(
            nome="R9 — e-mail lembrado nas mensagens seguintes",
            mensagens=["Sou bruno.unico@example.com", "Quanto custa o gerador GD-60?"],
            esperado=(
                "A 1ª mensagem (só o e-mail) recebe resposta fixa, sem LLM; na 2ª "
                "continua esporadico (o e-mail fica na conversa), apesar da intenção "
                "de compra."
            ),
            perfil_esperado="esporadico",
        ),
        Cenario(
            nome="R10 — mensagem só com o e-mail: resposta fixa, sem LLM",
            mensagens=["Meu e-mail é carla.antiga@example.com"],
            esperado=(
                "Resposta fixa agradecendo (sem dizer se há cadastro), backend "
                "resposta_fixa; perfil esporadico no painel."
            ),
            resposta_contem=["Anotei o seu e-mail"],
            resposta_nao_contem=["cadastro"],
            perfil_esperado="esporadico",
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


def _novas_linhas_de_log(log_path: Path, offset: int, conversation_id: str) -> list[dict]:
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
        # Desde 2026-09-25 o backend grava o `conversation_id` em cada linha:
        # só entram as da conversa do cenário (o navegador pode ficar em uso
        # durante o teste). Se o campo vier vazio, a linha fica de fora e o
        # cenário reprova por falta de log — sinal de que essa correção
        # regrediu.
        if registro.get("conversation_id") != conversation_id:
            continue
        registros.append(registro)
    return registros


def _veredito(
    cenario: Cenario,
    logs: list[dict],
    resposta: str,
    done: dict | None = None,
    conversa: dict | None = None,
) -> tuple[str, list[str]]:
    verifica_algo = (
        cenario.resultado_vendas is not None
        or cenario.resposta_contem
        or cenario.resposta_nao_contem
        or cenario.resposta_contem_algum
        or cenario.perfil_esperado
        or cenario.historico_esperado is not None
        or cenario.esperar_resumo
    )
    if not verifica_algo:
        return "—", []
    problemas = _problemas_vendas(cenario, logs) if cenario.resultado_vendas is not None else []
    problemas += [f"resposta sem {t!r}" for t in cenario.resposta_contem if t not in resposta]
    problemas += [f"resposta com {t!r}" for t in cenario.resposta_nao_contem if t in resposta]
    if cenario.resposta_contem_algum and not any(
        t.lower() in resposta.lower() for t in cenario.resposta_contem_algum
    ):
        problemas.append(f"resposta sem nenhum de {cenario.resposta_contem_algum}")
    if cenario.perfil_esperado:
        obtido = (done or {}).get("perfil_usuario")
        if obtido != cenario.perfil_esperado:
            problemas.append(f"perfil={obtido!r}, esperado {cenario.perfil_esperado!r}")
    if cenario.historico_esperado is not None or cenario.esperar_resumo:
        if conversa is None:
            problemas.append("GET /api/chat/conversations/{id} não devolveu a conversa")
        else:
            total = len(conversa.get("mensagens", []))
            if cenario.historico_esperado is not None and total != cenario.historico_esperado:
                problemas.append(
                    f"{total} mensagens gravadas, esperado {cenario.historico_esperado}"
                )
            resumo = conversa.get("resumo") or ""
            if cenario.esperar_resumo and not resumo:
                problemas.append("resumo não foi gerado")
            problemas += [f"resumo sem {t!r}" for t in cenario.resumo_contem if t not in resumo]
    return ("PASSOU" if not problemas else "FALHOU"), problemas


def _problemas_vendas(cenario: Cenario, logs: list[dict]) -> list[str]:
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
    return problemas


def _obter_conversa(cliente: httpx.Client, base_url: str, conversation_id: str) -> dict | None:
    try:
        resposta = cliente.get(f"{base_url}/api/chat/conversations/{conversation_id}")
    except httpx.HTTPError:
        return None
    return resposta.json() if resposta.status_code == 200 else None


def _esperar_resumo(
    cliente: httpx.Client, base_url: str, conversation_id: str, limite_s: float = 120.0
) -> float | None:
    """O resumo roda em segundo plano depois do `done`; espera ele aparecer.
    Devolve quanto tempo levou, ou None se não apareceu no prazo."""
    inicio = time.perf_counter()
    while time.perf_counter() - inicio < limite_s:
        conversa = _obter_conversa(cliente, base_url, conversation_id)
        if conversa and conversa.get("resumo"):
            return time.perf_counter() - inicio
        time.sleep(2)
    return None


def _rodar_cenario(
    cliente: httpx.Client, base_url: str, log_path: Path, cenario: Cenario
) -> tuple[str, list[str]]:
    linhas = [f"### {cenario.nome}", "", f"**Esperado:** {cenario.esperado}", ""]
    # Cada cenário numa conversa nova (UUID próprio) para o histórico curto
    # do roteador não vazar de um cenário para o outro.
    conversation_id = str(uuid.uuid4())
    logs_ultima: list[dict] = []
    texto_ultima = ""
    done_ultima: dict | None = None
    for indice, mensagem in enumerate(cenario.mensagens, start=1):
        if cenario.esperar_resumo and indice == len(cenario.mensagens):
            espera = _esperar_resumo(cliente, base_url, conversation_id)
            linhas.append(
                f"_Resumo em segundo plano: pronto em {espera:.0f}s._"
                if espera is not None
                else "_Resumo em segundo plano: não apareceu em 120 s._"
            )
            linhas.append("")
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
        texto_ultima = texto
        done_ultima = done

        linhas.append(f"**Mensagem {indice}:** {mensagem}")
        linhas.append("")
        if erro:
            linhas.append(f"- ⚠️ erro: `{erro}`")
        if done:
            linhas.append(
                f"- domínio `{done.get('domain')}` · backend `{done.get('backend_used')}` · "
                f"motivo `{done.get('escalation_reason')}` · modelo `{done.get('model_name')}` · "
                f"classificador `{done.get('router_provider')}` · "
                f"rag_retrieval_ms `{done.get('rag_retrieval_ms')}` · total {duracao:.1f}s"
            )
            if done.get("perfil_usuario"):
                linhas.append(
                    f"- perfil `{done.get('perfil_usuario')}` ({done.get('perfil_motivo')})"
                )
        linhas += ["", "Resposta do assistente:", "", "```text", texto.strip() or "(vazia)", "```"]
        consultas = [r for r in logs if r.get("message") != "router_decision"]
        if consultas:
            linhas += ["", "Logs do backend (vendas/memória/erros):", "", "```json"]
            for registro in consultas:
                resumo = {k: v for k, v in registro.items() if k not in {"level", "logger"}}
                linhas.append(json.dumps(resumo, ensure_ascii=False, indent=2))
            linhas.append("```")
        linhas.append("")

    conversa = None
    if cenario.historico_esperado is not None or cenario.esperar_resumo:
        conversa = _obter_conversa(cliente, base_url, conversation_id)
        if conversa is not None:
            linhas.append(
                f"- Conversa gravada: {len(conversa.get('mensagens', []))} mensagens · "
                f"resumo: {conversa.get('resumo') or '(nenhum)'}"
            )
            linhas.append("")
    veredito, problemas = _veredito(cenario, logs_ultima, texto_ultima, done_ultima, conversa)
    linhas.append(f"**Veredito automático:** {veredito}")
    linhas += [f"- {problema}" for problema in problemas]
    linhas.append("")
    return veredito, linhas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--suite", choices=sorted([*SUITES, "mcp_b2b"]), default=SUITE_ATUAL)
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

    placar: dict[str, int] = {}
    if args.suite == "mcp_b2b":
        # Não é chat: verificações de autenticação/HTTPS do MCP B2B, em
        # módulo próprio (scripts/teste_local_mcp_b2b.py).
        from teste_local_mcp_b2b import rodar_verificacoes

        placar, linhas = rodar_verificacoes()
        relatorio += linhas
        cenarios = []
    else:
        relatorio += ["## 2. Cenários de chat", ""]
        cenarios = [c for c in SUITES[args.suite] if not args.so or c.nome.startswith(args.so)]
    with httpx.Client(timeout=httpx.Timeout(180.0, connect=5.0)) as cliente:
        try:
            if cenarios:
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
        ("Placar das verificações: " if args.suite == "mcp_b2b" else "Placar dos cenários: ")
        + (", ".join(f"{k}: {v}" for k, v in sorted(placar.items())) or "nenhum rodou"),
        "",
    ]
    relatorio += [
        "## 3. Observações do testador",
        "",
        (
            "<!-- Suíte memoria: teste também no navegador — converse no chat, feche e "
            "reabra a página: as mensagens anteriores devem reaparecer (R9). No painel de "
            "métricas (⚙️) de cada resposta aparece o Perfil (R10). -->"
            if args.suite == "memoria"
            else "<!-- Opcional: o que você viu no chat do navegador, algo estranho na "
            "resposta, etc. -->"
        ),
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
