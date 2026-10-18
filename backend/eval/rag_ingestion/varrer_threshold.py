"""Varredura offline de `score_threshold` e `top_k` (Etapa 4, Fase 10 —
`docs/EVALUATION.md` Seção 2.1).

Não reingere nada e não consulta o Qdrant: lê `resultados_etapa1.json` (ou o
vencedor de `resultados_etapa2.json` / `resultados_etapa3.json`), que guarda
`(fonte, score)` pareado por pergunta, e recalcula as métricas para cada
threshold candidato. Por isso roda em milissegundos e pode varrer quantos
pontos se quiser.

**Exige que a rodada-base tenha usado um threshold baixo.** Não se pode
recuperar, offline, um documento que a busca original já cortou — então a
rodada que alimenta esta varredura precisa ter sido feita com
`--score-threshold 0.0` (e um `--top-k` pelo menos igual ao maior que se
quer avaliar). O script checa isso e recusa rodar sobre uma base cortada,
em vez de produzir uma tabela silenciosamente truncada.

Uso (a partir de `backend/`; não exige nada no ar):

    .venv/bin/python eval/rag_ingestion/varrer_threshold.py
    .venv/bin/python eval/rag_ingestion/varrer_threshold.py \
        --entrada eval/rag_ingestion/resultados_etapa3.json \
        --saida eval/rag_ingestion/varredura_threshold_etapa4.json
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


def recomendar_parametros(linhas: list[dict], sep: dict) -> dict:
    """Escolhe `(top_k, score_threshold)` ótimos na grade varrida.

    Prioriza maximizar `recall@5 + acerto_negativas` (equilíbrio entre não
    perder fonte positiva — evitando falso escalonamento ao modelo externo —
    e recusar casos sem resposta no corpus), desempatando por `ndcg@10`,
    `mrr`, `top_k=5` e proximidade ao ponto médio do intervalo separável.
    """
    ponto_medio: float | None = None
    if sep.get("separavel"):
        menor_pos = sep["menor_score_maximo_positivas"]
        maior_neg = sep["maior_score_maximo_negativas"]
        ponto_medio = round((menor_pos + maior_neg) / 2, 4)

    def chave(linha: dict) -> tuple:
        r5 = linha.get("recall@5") or 0.0
        an = linha.get("acerto_negativas") or 0.0
        vazio_pos = linha.get("taxa_vazio_positivas") or 0.0
        ndcg = linha.get("ndcg@10") or 0.0
        mrr = linha.get("mrr") or 0.0
        dist_meio = abs(linha["score_threshold"] - ponto_medio) if ponto_medio is not None else 0.0
        prefere_top5 = 0 if linha["top_k"] == 5 else 1
        return (
            -round(r5 + an, 6),
            round(vazio_pos, 6),
            -round(ndcg, 6),
            -round(mrr, 6),
            prefere_top5,
            round(dist_meio, 6),
        )

    melhor = min(linhas, key=chave)
    return {
        **melhor,
        "threshold_ponto_medio": ponto_medio,
    }


def _extrair_base(base: dict, ponto_id: str | None) -> tuple[dict, list[dict]]:
    """Extrai `(config, itens)` tanto do JSON da Etapa 1 quanto dos JSONs de
    grade das Etapas 2 e 3 (`candidatos` / `pontos`)."""
    if "config" in base and "itens" in base:
        return base["config"], base["itens"]

    colecao = base.get("pontos") or base.get("candidatos") or []
    if not colecao:
        raise ValueError("JSON de entrada não contém 'itens', 'pontos' nem 'candidatos'")

    alvo_id = ponto_id or (base.get("vencedor") or {}).get("id")
    escolhido = next((p for p in colecao if p.get("id") == alvo_id), colecao[0])
    config = {
        "id": escolhido.get("id"),
        "embedding_model": escolhido.get("embedding_model") or base.get("embedding_model"),
        "chunk_size": escolhido.get("chunk_size"),
        "chunk_overlap": escolhido.get("chunk_overlap"),
        "unidade": escolhido.get("unidade", "tokens"),
        "score_threshold": 0.0,
        "top_k": 10,
    }
    return config, escolhido["itens"]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Etapa 4 — varredura offline de threshold/top_k")
    parser.add_argument("--entrada", type=Path, default=ENTRADA)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument(
        "--ponto",
        default=None,
        help="ID do ponto/candidato quando a entrada é resultados_etapa2/3.json (padrão: vencedor)",
    )
    args = parser.parse_args(argv[1:])

    if not args.entrada.exists():
        print(
            f"ERRO: {args.entrada.name} não existe. Rode a Etapa 1 ou Etapa 3 primeiro:\n"
            "  .venv/bin/python eval/rag_ingestion/run_etapa1.py "
            "--score-threshold 0.0 --top-k 10",
            file=sys.stderr,
        )
        return 1

    base = json.loads(args.entrada.read_text(encoding="utf-8"))
    config_base, itens = _extrair_base(base, args.ponto)
    threshold_base = config_base.get("score_threshold", 0.0)
    if threshold_base > THRESHOLD_MAXIMO_DA_BASE:
        print(
            f"ERRO: a rodada-base usou score_threshold={threshold_base}, acima de "
            f"{THRESHOLD_MAXIMO_DA_BASE}. A varredura não pode recuperar documentos que a "
            "busca original já cortou. Rode de novo com --score-threshold 0.0 --top-k 10.",
            file=sys.stderr,
        )
        return 1

    linhas = varrer(itens)
    sep = separabilidade(itens)
    rec = recomendar_parametros(linhas, sep)

    print(f"Base: {args.entrada.name} ({config_base.get('embedding_model')})")
    if config_base.get("id"):
        print(
            f"Ponto: {config_base['id']} (chunk={config_base.get('chunk_size')}"
            f"/{config_base.get('chunk_overlap')})"
        )
    print(f"n = {len(itens)} perguntas\n")

    print("=== Existe threshold que separe positivas de negativas? ===")
    print(f"  menor score máximo entre positivas: {sep.get('menor_score_maximo_positivas')}")
    print(f"  maior score máximo entre negativas: {sep.get('maior_score_maximo_negativas')}")
    if sep.get("separavel"):
        print(
            f"  SIM — há um corte que acerta positivas e negativas "
            f"(ponto médio={rec['threshold_ponto_medio']}, recomendado={rec['score_threshold']})."
        )
    else:
        print(
            f"  NÃO — {sep.get('positivas_abaixo_da_pior_negativa')} de {sep.get('n_positivas')} "
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

    args.saida.write_text(
        json.dumps(
            {
                "base": args.entrada.name,
                "config_base": config_base,
                "separabilidade": sep,
                "recomendacao": rec,
                "varredura": linhas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nResultado: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
