"""Varredura offline de `score_threshold` e `top_k` (Etapa 4, Fase 10 —
`docs/EVALUATION.md` Seção 2.1).

Não reingere nada e não consulta o Qdrant: lê `resultados_etapa1.json`, que
guarda `(fonte, score)` pareado por pergunta, e recalcula as métricas para
cada threshold candidato. Por isso roda em milissegundos e pode varrer
quantos pontos se quiser.

**Exige que a rodada-base tenha usado um threshold baixo.** Não se pode
recuperar, offline, um documento que a busca original já cortou — então a
rodada que alimenta esta varredura precisa ter sido feita com
`--score-threshold 0.0` (e um `--top-k` pelo menos igual ao maior que se
quer avaliar). O script checa isso e recusa rodar sobre uma base cortada,
em vez de produzir uma tabela silenciosamente truncada.

Uso (a partir de `backend/`; não exige nada no ar):

    .venv/bin/python eval/rag_ingestion/run_etapa1.py --score-threshold 0.0 --top-k 10
    .venv/bin/python eval/rag_ingestion/varrer_threshold.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from metricas import ResultadoPergunta, aplicar_threshold, avaliar_conjunto  # noqa: E402

ENTRADA = BASE_DIR / "resultados_etapa1.json"
SAIDA = BASE_DIR / "varredura_threshold.json"

THRESHOLDS = (0.0, 0.35, 0.45, 0.50, 0.55, 0.58, 0.60, 0.62, 0.65, 0.70, 0.75)
TOP_KS = (3, 5, 10)

# A rodada-base precisa ter sido feita com um threshold no máximo deste
# valor, senão a varredura mede sobre uma lista já cortada.
THRESHOLD_MAXIMO_DA_BASE = 0.01


class BaseCortadaError(RuntimeError):
    """A rodada-base usou um `score_threshold` alto demais para varrer."""


def varrer(itens: list[dict]) -> list[dict]:
    linhas = []
    for top_k in TOP_KS:
        for threshold in THRESHOLDS:
            resultados = [
                ResultadoPergunta(
                    id=item["id"],
                    negativa=item["negativa"],
                    recuperadas=aplicar_threshold(
                        [(r["fonte"], r["score"]) for r in item["recuperadas"]],
                        threshold,
                        top_k=top_k,
                    ),
                    aceitas=set(item["fontes_aceitas"]),
                )
                for item in itens
            ]
            agregado = avaliar_conjunto(resultados)
            linhas.append(
                {
                    "top_k": top_k,
                    "score_threshold": threshold,
                    "recall@5": agregado["recall"]["@5"],
                    "ndcg@10": agregado["ndcg@10"],
                    "mrr": agregado["mrr"],
                    "taxa_vazio_positivas": agregado["taxa_vazio_positivas"],
                    "acerto_negativas": agregado["acerto_negativas"],
                }
            )
    return linhas


def separabilidade(itens: list[dict]) -> dict:
    """Mede se existe algum threshold capaz de separar positivas de negativas.

    Compara o **menor** score máximo entre as positivas com o **maior**
    entre as negativas. Se o primeiro for maior que o segundo, existe um
    corte que acerta tudo; se não, nenhum threshold resolve, e o problema
    está no modelo de embedding, não no parâmetro.
    """
    pos = [i["score_maximo"] for i in itens if not i["negativa"] and i["score_maximo"] is not None]
    neg = [i["score_maximo"] for i in itens if i["negativa"] and i["score_maximo"] is not None]
    if not pos or not neg:
        return {"separavel": None, "motivo": "conjunto sem positivas ou sem negativas"}
    menor_pos, maior_neg = min(pos), max(neg)
    return {
        "menor_score_maximo_positivas": round(menor_pos, 4),
        "maior_score_maximo_negativas": round(maior_neg, 4),
        "separavel": menor_pos > maior_neg,
        "positivas_abaixo_da_pior_negativa": sum(1 for s in pos if s <= maior_neg),
        "n_positivas": len(pos),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Etapa 4 — varredura offline de threshold/top_k")
    parser.add_argument("--entrada", type=Path, default=ENTRADA)
    args = parser.parse_args(argv[1:])

    if not args.entrada.exists():
        print(
            f"ERRO: {args.entrada.name} não existe. Rode a Etapa 1 primeiro:\n"
            "  .venv/bin/python eval/rag_ingestion/run_etapa1.py "
            "--score-threshold 0.0 --top-k 10",
            file=sys.stderr,
        )
        return 1

    base = json.loads(args.entrada.read_text(encoding="utf-8"))
    threshold_base = base["config"]["score_threshold"]
    if threshold_base > THRESHOLD_MAXIMO_DA_BASE:
        print(
            f"ERRO: a rodada-base usou score_threshold={threshold_base}, acima de "
            f"{THRESHOLD_MAXIMO_DA_BASE}. A varredura não pode recuperar documentos que a "
            "busca original já cortou. Rode de novo com --score-threshold 0.0 --top-k 10.",
            file=sys.stderr,
        )
        return 1

    itens = base["itens"]
    linhas = varrer(itens)
    sep = separabilidade(itens)

    print(f"Base: {args.entrada.name} ({base['config']['embedding_model']})")
    print(f"n = {len(itens)} perguntas\n")

    print("=== Existe threshold que separe positivas de negativas? ===")
    print(f"  menor score máximo entre positivas: {sep['menor_score_maximo_positivas']}")
    print(f"  maior score máximo entre negativas: {sep['maior_score_maximo_negativas']}")
    if sep["separavel"]:
        print("  SIM — há um corte que acerta positivas e negativas.")
    else:
        print(
            f"  NÃO — {sep['positivas_abaixo_da_pior_negativa']} de {sep['n_positivas']} "
            "positivas pontuam abaixo da pior negativa.\n"
            "  Nenhum score_threshold resolve: o problema está no modelo de embedding\n"
            "  (Etapa 2), não neste parâmetro."
        )

    print("\n=== Varredura ===")
    print(
        f"{'top_k':>5} {'thr':>5} {'R@5':>6} {'nDCG@10':>8} "
        f"{'MRR':>6} {'vazio_p':>8} {'acerto_n':>9}"
    )
    for linha in linhas:

        def f(valor: float | None) -> str:
            return f"{valor:.3f}" if valor is not None else "  —  "

        print(
            f"{linha['top_k']:>5} {linha['score_threshold']:>5.2f} "
            f"{f(linha['recall@5']):>6} {f(linha['ndcg@10']):>8} {f(linha['mrr']):>6} "
            f"{f(linha['taxa_vazio_positivas']):>8} {f(linha['acerto_negativas']):>9}"
        )

    SAIDA.write_text(
        json.dumps(
            {
                "base": args.entrada.name,
                "config_base": base["config"],
                "separabilidade": sep,
                "varredura": linhas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nResultado: {SAIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
