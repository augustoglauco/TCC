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
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BACKEND = RAIZ / "backend"
FRONTEND = RAIZ / "frontend"
LIMITE_TESTES = 80  # acima disso a seleção não ajuda: roda a suíte inteira


def sh(cmd: list[str], cwd: Path = RAIZ, dry: bool = False) -> int:
    print(f"\n$ ({cwd.relative_to(RAIZ) or '.'}) {' '.join(cmd)}", flush=True)
    if dry:
        return 0
    return subprocess.run(cmd, cwd=cwd).returncode


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
        ruff = str(BACKEND / ".venv/bin/ruff")
        rodar("ruff check (backend)", [ruff, "check", *rel], BACKEND)
        rodar("ruff format (backend)", [ruff, "format", "--check", *rel], BACKEND)
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
        rodar("ruff (cliente-b2b)", ["uv", "run", "ruff", "check", *rel], RAIZ / "cliente-b2b")

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
        rodar("doc-drift", ["repowise", "doc-drift", "--check",
                            "--kind", "path", "--kind", "link", "--kind", "anchor",
                            "--kind", "command", "--kind", "symbol",
                            "--baseline", ".doc-drift-baseline.json",
                            "--since", "HEAD"])
    else:
        print("\ndocs: nenhum .md alterado nem arquivo removido — gate pulado.")

    print("\n" + ("FALHOU: " + ", ".join(falhas) if falhas else "OK: checagens passaram."))
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
