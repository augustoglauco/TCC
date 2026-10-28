"""Consolida o resultado da Etapa 7 (baseline MiniLM 800/100 x vencedora
bge-m3 768/115) em `etapa7.json`, o arquivo que a página `/avaliacao` lê.

Só agrega os resultados já gravados por `run_eval.py` (sem LLM, sem GPU):

    .venv/bin/python eval/rag_quality/consolidar_etapa7.py
"""

import json
import re
import statistics
from pathlib import Path

BASE = Path(__file__).parent
BRACOS = (
    (
        "baseline",
        "MiniLM 800/100 (2026-10-01)",
        "results_e_base_resp.json",
        "results_e_base_neg.json",
    ),
    ("vencedora", "bge-m3 768/115, top_k 5", "results_d_B_resp.json", "results_d_B_neg.json"),
)


def _ler(nome: str) -> dict:
    return json.loads((BASE / nome).read_text(encoding="utf-8"))


_RECUSA = re.compile(
    r"n[ãa]o (encontr|localiz|consegui|h[áa] informa|possuo|tenho)|atendente"
    r"|n[ãa]o consta|n[ãa]o est[áa] (dispon|especific)",
    re.IGNORECASE,
)


def _virou_recusa(texto: str) -> bool:
    # Mesmo critério do EVALUATION.md (Etapa 7): marcadores amplos de "não achei".
    return _RECUSA.search(texto or "") is not None


def _latencias_s(casos: list[dict]) -> list[float]:
    return [c["latencia_geracao"]["total_ms"] / 1000 for c in casos if c.get("latencia_geracao")]


def _p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[-1]


def _braco(chave: str, rotulo: str, arq_resp: str, arq_neg: str) -> dict:
    resp, neg = _ler(arq_resp), _ler(arq_neg)
    casos = resp["casos"]
    notas = [c["nota_llm_judge"]["nota"] for c in casos if c.get("nota_llm_judge")]
    lat = _latencias_s(casos)
    sem = neg["casos_sem_resposta"]
    return {
        "braco": chave,
        "rotulo": rotulo,
        "colecao": resp["configuracao"].get("collection"),
        "respondiveis": len(casos),
        "nota_media": round(statistics.mean(notas), 3),
        "fonte_correta": sum(1 for c in casos if c["fonte_correta"]),
        "recusas_indevidas": sum(1 for c in casos if _virou_recusa(c["resposta_gerada"])),
        "sem_resposta": len(sem),
        "negativas_recusou": sum(1 for c in sem if c["recusou"]),
        "negativas_alucinou": sum(1 for c in sem if c["alucinou"]),
        "latencia_media_s": round(statistics.mean(lat), 2),
        "latencia_p95_s": round(_p95(lat), 2),
    }


def main() -> None:
    saida = {"bracos": [_braco(*b) for b in BRACOS]}
    (BASE / "etapa7.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(saida, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
