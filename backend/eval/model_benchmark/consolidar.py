"""Relatório consolidado do benchmark (Fase 10, item 17): lê
`results/<id>.json` e imprime, em Markdown, a tabela por modelo e o teste de
McNemar exato entre todos os pares (os quatro modelos respondem aos mesmos
itens, então o pareado é o teste certo; o IC de Wilson só descreve cada um).

    .venv/bin/python eval/model_benchmark/consolidar.py > relatorio.md
"""

import itertools
import json
from pathlib import Path

from scipy.stats import binomtest, wilcoxon

RESULTS = Path(__file__).parent / "results"
EVAL_DIR = Path(__file__).parent.parent
MODELOS = ("gemma4-12b-q4", "gemma4-e4b-q8", "qwen25-vl-3b", "qwen25-vl-7b")
COLUNAS = (
    ("roteador_acuracia", "roteador"),
    ("rag_nota_media", "RAG nota"),
    ("rag_fonte_correta_taxa", "RAG fonte"),
    ("injecao_resistencia", "injeção"),
    ("latencia_p95_s", "lat. p95 (s)"),
)


def _ids_roteador() -> set[int]:
    """Casos do placar principal do roteador (não ambíguos, não descartados)."""
    dados = json.loads((EVAL_DIR / "router_intents" / "dataset.json").read_text(encoding="utf-8"))
    return {
        c["id"]
        for c in dados["casos"]
        if not c.get("ambiguo") and (c.get("revisao") or {}).get("status") != "descartado"
    }


def _acertos_roteador(item: dict, universo: set[int]) -> dict[str, bool]:
    erros = {e["id"] for e in item["erros"] if not e["ambiguo"]}
    return {str(i): i not in erros for i in universo}


def _desfechos(itens: dict, universo_roteador: set[int]) -> dict[str, dict[str, bool]]:
    """etapa -> {id do item: acertou}."""
    saida: dict[str, dict[str, bool]] = {}
    if "roteador" in itens:
        saida["roteador"] = _acertos_roteador(itens["roteador"], universo_roteador)
    if "injecao" in itens:
        saida["injeção (resistiu)"] = {
            str(c["id"]): not c["comprometido"] for c in itens["injecao"]["casos"]
        }
    if "imagem" in itens:
        saida["imagem (portfólio)"] = {
            str(c["id"]): bool(c["acerto_portfolio"])
            for c in itens["imagem"]["casos"]
            if c.get("acerto_portfolio") is not None
        }
    return saida


def mcnemar_exato(a: dict[str, bool], b: dict[str, bool]) -> tuple[int, int, float]:
    comuns = a.keys() & b.keys()
    so_a = sum(1 for k in comuns if a[k] and not b[k])
    so_b = sum(1 for k in comuns if b[k] and not a[k])
    if so_a + so_b == 0:
        return so_a, so_b, 1.0
    return so_a, so_b, binomtest(so_a, so_a + so_b, 0.5).pvalue


def _notas_rag(itens: dict) -> dict[str, int]:
    return {
        str(c["id"]): c["nota_llm_judge"]["nota"]
        for c in itens.get("rag", {}).get("casos", [])
        if (c.get("nota_llm_judge") or {}).get("nota") is not None
    }


def _imprimir_wilcoxon(dados: dict[str, dict]) -> None:
    """RAG: a fonte recuperada é a mesma nos quatro (independe do gerador),
    então o que separa os modelos é a nota do juiz — Wilcoxon pareado."""
    notas = {m: _notas_rag(d["itens"]) for m, d in dados.items()}
    print("\n### RAG (nota do juiz, Wilcoxon pareado)\n")
    print("| A | B | média A | média B | n | p |\n|---|---|---|---|---|---|")
    for a, b in itertools.combinations(dados, 2):
        ids = sorted(notas[a].keys() & notas[b].keys())
        xs, ys = [notas[a][i] for i in ids], [notas[b][i] for i in ids]
        if not ids or xs == ys:
            continue
        p = wilcoxon(xs, ys).pvalue
        ma, mb = sum(xs) / len(xs), sum(ys) / len(ys)
        print(f"| {a} | {b} | {ma:.2f} | {mb:.2f} | {len(ids)} | {p:.4f} |")


def _carregar() -> dict[str, dict]:
    return {
        m: json.loads((RESULTS / f"{m}.json").read_text(encoding="utf-8"))
        for m in MODELOS
        if (RESULTS / f"{m}.json").exists()
    }


def _imprimir_tabela(dados: dict[str, dict]) -> None:
    print("| Modelo | " + " | ".join(r for _, r in COLUNAS) + " |")
    print("|---" * (len(COLUNAS) + 1) + "|")
    for modelo, d in dados.items():
        celulas = [str(d["metricas"].get(chave, "—")) for chave, _ in COLUNAS]
        print(f"| {modelo} | " + " | ".join(celulas) + " |")


def _imprimir_pares(dados: dict[str, dict]) -> None:
    universo = _ids_roteador()
    desfechos = {m: _desfechos(d["itens"], universo) for m, d in dados.items()}
    for etapa in sorted({e for v in desfechos.values() for e in v}):
        print(
            f"\n### {etapa}\n\n| A | B | só A acertou | só B acertou | p |\n|---|---|---|---|---|"
        )
        for a, b in itertools.combinations(dados, 2):
            if etapa in desfechos[a] and etapa in desfechos[b]:
                sa, sb, p = mcnemar_exato(desfechos[a][etapa], desfechos[b][etapa])
                print(f"| {a} | {b} | {sa} | {sb} | {p:.4f} |")


def main() -> None:
    dados = _carregar()
    print("# Benchmark consolidado\n")
    _imprimir_tabela(dados)
    print("\n## McNemar exato entre pares")
    print("\n6 pares por etapa: com Bonferroni, p < 0,0083 para valer a 5%.")
    _imprimir_pares(dados)
    _imprimir_wilcoxon(dados)


if __name__ == "__main__":
    main()
