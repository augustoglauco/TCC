#!/usr/bin/env python3
"""Checagens de pré-commit proporcionais à mudança (docs/CONVENTIONS.md).

Olha só o que mudou em relação ao HEAD (staged, unstaged e novos) e roda:
  - backend:  ruff nos .py alterados + pytest só dos testes que tocam os
              módulos alterados (importação direta ou por um importador);
  - frontend: eslint/prettier nos arquivos alterados + `vitest related`;
  - docs:     gate de deriva só quando há .md alterado ou arquivo apagado/
              renomeado;
Graphify e GitNexus NÃO rodam aqui: são ferramentas de consulta (o hook
post-commit já reconstrói o grafo do Graphify).

Uso: scripts/checar_mudanca.py [--dry-run] [--full-backend] [--e2e]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
FRONTEND = RAIZ / "frontend"
# Um ruff só para os dois pacotes Python: o `cliente-b2b` configura as mesmas
# regras no seu pyproject.toml mas não declara o ruff como dependência, então
# `uv run ruff` falha lá dentro.
RUFF = str(BACKEND / ".venv/bin/ruff")
LIMITE_TESTES = 80  # acima disso a seleção não ajuda: roda a suíte inteira
BASELINE = ".doc-drift-baseline.json"
LIMITE_CONFIANCA = 0.7  # mesmo default do `--fail-on-confidence` do repowise


def sh(cmd: list[str], cwd: Path = RAIZ, dry: bool = False) -> int:
    print(f"\n$ ({cwd.relative_to(RAIZ) or '.'}) {' '.join(cmd)}", flush=True)
    if dry:
        return 0
    return subprocess.run(cmd, cwd=cwd).returncode


def doc_drift(dry: bool = False) -> str | None:
    """Roda o `doc-drift` e devolve o rótulo da falha, ou None se passou.

    O `--baseline` do repowise impede a falha mas continua imprimindo os
    achados aceitos (34 hoje), o que afoga um achado novo no meio do ruído.
    Aqui o baseline é aplicado por nós: só o que é novo aparece.
    """
    cmd = ["repowise", "doc-drift", "--check",
           "--kind", "path", "--kind", "link", "--kind", "anchor",
           "--kind", "command", "--kind", "symbol",
           "--since", "HEAD", "--format", "json"]
    print(f"\n$ (.) {' '.join(cmd)}", flush=True)
    if dry:
        return None

    proc = subprocess.run(cmd, cwd=RAIZ, capture_output=True, text=True)
    try:
        achados = json.loads(proc.stdout)["findings"]
    except (ValueError, KeyError):
        print(proc.stdout or proc.stderr, flush=True)
        return "doc-drift (saída ilegível)"

    aceitos = {
        (e["file_path"], e["kind"], e["target"])
        for e in json.loads((RAIZ / BASELINE).read_text())["entries"]
    }
    novos = [a for a in achados
             if (a["file_path"], a["kind"], a["target"]) not in aceitos
             and a["confidence"] >= LIMITE_CONFIANCA]

    for a in novos:
        print(f"  {a['file_path']}:{a['line_number']} {a['confidence']:.2f} "
              f"{a['kind']}  {a['reason']}", flush=True)
    print(f"docs: {len(novos)} achado(s) novo(s); "
          f"{len(achados) - len(novos)} já aceitos em {BASELINE} (omitidos).")

    # O detector de símbolo já pegou um módulo fantasma aqui (ver
    # docs/ROADMAP.md, revisão de 2026-10-15) e o baseline guarda 24 achados
    # desse tipo. Se ele volta vazio, parou de rodar — e o item 11 do
    # checklist estaria dando garantia falsa em silêncio.
    if any(k == "symbol" for _, k, _ in aceitos) and not any(
        a["kind"] == "symbol" for a in achados
    ):
        print("docs: AVISO — nenhum achado 'symbol', mas o baseline tem 24. "
              "A checagem de símbolo não está rodando; não pode o baseline.")

    return "doc-drift" if novos else None


def alterados() -> tuple[list[str], list[str]]:
    """(existentes, removidos/renomeados-origem) relativos à raiz."""
    saida = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=RAIZ, capture_output=True, text=True, check=True,
    ).stdout
    existentes, removidos = [], []
    itens = saida.split("\0")
    i = 0
    while i < len(itens):
        item = itens[i]
        i += 1
        if len(item) < 4:
            continue
        xy, caminho = item[:2], item[3:]
        if "R" in xy:  # rename: o próximo campo é a origem
            removidos.append(itens[i])
            i += 1
        if "D" in xy:
            removidos.append(caminho)
        elif (RAIZ / caminho).is_file():
            existentes.append(caminho)
    return existentes, removidos


def modulo(caminho: str) -> str | None:
    """backend/src/app/a/b.py -> app.a.b"""
    if not caminho.startswith("backend/src/") or not caminho.endswith(".py"):
        return None
    partes = Path(caminho[len("backend/src/"):]).with_suffix("").parts
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)


def importa(texto: str, mod: str) -> bool:
    pai, _, nome = mod.rpartition(".")
    padrao = rf"(?:from|import)\s+{re.escape(mod)}\b|from\s+{re.escape(pai)}\s+import\s+[^\n]*\b{re.escape(nome)}\b"
    return re.search(padrao, texto) is not None


def testes_afetados(py_alterados: list[str]) -> set[str]:
    mods = {m for c in py_alterados if (m := modulo(c))}
    selecionados = {
        str(Path(c).relative_to("backend"))
        for c in py_alterados
        if c.startswith("backend/tests/test_")
    }
    if not mods:
        return selecionados
    fontes = {p: p.read_text(encoding="utf-8", errors="replace")
              for p in (BACKEND / "src").rglob("*.py")}
    testes = {p: p.read_text(encoding="utf-8", errors="replace")
              for p in (BACKEND / "tests").glob("test_*.py")}
    # um nível de importadores: quem importa o módulo alterado também conta
    alvo = set(mods)
    for p, txt in fontes.items():
        if any(importa(txt, m) for m in mods):
            m = modulo(str(p.relative_to(RAIZ)))
            if m:
                alvo.add(m)
    for p, txt in testes.items():
        if any(importa(txt, m) for m in alvo):
            selecionados.add(str(p.relative_to(BACKEND)))
    return selecionados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="só mostra o plano")
    ap.add_argument("--full-backend", action="store_true", help="pytest completo")
    ap.add_argument("--e2e", action="store_true", help="inclui Playwright (smoke)")
    a = ap.parse_args()

    existentes, removidos = alterados()
    if not existentes and not removidos:
        print("Nada alterado em relação ao HEAD.")
        return 0

    py = [c for c in existentes if c.startswith("backend/") and c.endswith(".py")]
    py_cli = [c for c in existentes if c.startswith("cliente-b2b/") and c.endswith(".py")]
    fe = [c for c in existentes if c.startswith("frontend/")
          and re.search(r"\.(tsx?|jsx?|mjs)$", c)]
    md = [c for c in existentes if c.endswith(".md") and not c.startswith("graphify-out/")]
    falhas: list[str] = []

    def rodar(rotulo: str, cmd: list[str], cwd: Path = RAIZ) -> None:
        if sh(cmd, cwd, a.dry_run) != 0:
            falhas.append(rotulo)

    if py:
        rel = [str(Path(c).relative_to("backend")) for c in py]
        rodar("ruff check (backend)", [RUFF, "check", *rel], BACKEND)
        rodar("ruff format (backend)", [RUFF, "format", "--check", *rel], BACKEND)
        testes = sorted(testes_afetados(py))
        pytest = [str(BACKEND / ".venv/bin/python"), "-m", "pytest", "-q",
                  "-m", "not gpu and not qdrant"]
        if a.full_backend or len(testes) > LIMITE_TESTES:
            print(f"\nbackend: suíte completa ({len(testes)} testes afetados).")
            rodar("pytest (backend, completo)", pytest, BACKEND)
        elif testes:
            print(f"\nbackend: {len(testes)} arquivo(s) de teste afetado(s).")
            rodar("pytest (backend, afetados)", [*pytest, *testes], BACKEND)
        else:
            print("\nbackend: nenhum teste referencia os módulos alterados.")

    if py_cli:
        rel = [str(Path(c).relative_to("cliente-b2b")) for c in py_cli]
        # Com cwd em cliente-b2b, o ruff do backend lê o [tool.ruff] de lá.
        rodar("ruff (cliente-b2b)", [RUFF, "check", *rel], RAIZ / "cliente-b2b")

    if fe:
        rel = [str(Path(c).relative_to("frontend")) for c in fe]
        rodar("prettier", ["npx", "prettier", "--check", *rel], FRONTEND)
        rodar("eslint", ["npx", "eslint", *rel], FRONTEND)
        # `related` segue o grafo de imports: só testes que tocam os arquivos.
        rodar("vitest related", ["npx", "vitest", "related", "--run",
                                 "--passWithNoTests", *rel], FRONTEND)
        if a.e2e:
            rodar("playwright smoke", ["npm", "run", "test:e2e:smoke"], FRONTEND)

    if md or removidos:
        rodar("repowise update", ["repowise", "update", "--working-tree"])
        if (falha := doc_drift(a.dry_run)) is not None:
            falhas.append(falha)
    else:
        print("\ndocs: nenhum .md alterado nem arquivo removido — gate pulado.")

    print("\n" + ("FALHOU: " + ", ".join(falhas) if falhas else "OK: checagens passaram."))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
