"""Carregador único do gabarito de RAG documentos para as Etapas 1–5 (R4, Fase 10).

Lê o conjunto canônico `eval/rag_quality/dataset.json` (o mesmo que a tela
`/admin/datasets` revisa e que `run_eval.py` lê) e devolve a estrutura que os
runners e `metricas.py` esperam: `{"dominio", "_pastas", "perguntas"}`. Assim a
revisão feita na tela vale direto para a grade, sem arquivo intermediário que
possa ficar desatualizado.

Regras de seleção (cada corte é contado em `relatorio`, nada some em silêncio):

- só `revisao.status` ∈ {aprovado, corrigido}; `--incluir-pendentes` libera
  `pendente` para ensaio, e o resultado NÃO vale como decisão;
- `descartado` e `duplicada_de` ficam de fora; `trecho_confere == False` só
  corta item ainda `pendente` (ensaio): o flag é um aviso automático para o
  revisor (casa o trecho com o texto extraído, e falha com erro de OCR ou
  quebra de linha), e a aprovação humana, feita com o trecho na tela, vale mais;
- `origem_ambigua` fica de fora: `ingest_file` grava só o basename em
  `source`, então um arquivo homônimo de outra pasta contaria como acerto;
- `sem_resposta` vira caso **negativo** (`fontes_aceitas` vazia): acerto é
  não devolver nada, e é com eles que se calibra o `score_threshold`.

`_pastas` é o corpus inteiro (toda pasta auditada), não só as pastas dos
positivos: negativas só significam algo contra o corpus completo, e ingerir
um subconjunto inflaria `Recall@k`.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATASET_CANONICO = BASE_DIR.parent / "rag_quality" / "dataset.json"
AUDITORIA = BASE_DIR / "auditoria_corpus.json"

DOMINIO_PADRAO = "suporte"
STATUS_VALIDOS = {"aprovado", "corrigido"}


class DatasetVazioError(RuntimeError):
    """Nenhum caso passou nos cortes (tipicamente: revisão ainda não feita)."""


def _pastas_do_corpus(auditoria: Path) -> list[str]:
    if not auditoria.exists():
        raise FileNotFoundError(
            f"{auditoria.name} não existe. Rode a Etapa 0 primeiro:\n"
            "  .venv/bin/python eval/rag_ingestion/auditar_corpus.py"
        )
    dados = json.loads(auditoria.read_text(encoding="utf-8"))
    return sorted({item["pasta"] for item in dados["itens_pastas"]})


def _motivo_de_corte(caso: dict[str, Any], incluir_pendentes: bool) -> str | None:
    status = (caso.get("revisao") or {}).get("status", "pendente")
    if status == "pendente" and not incluir_pendentes:
        return "pendente"
    if status == "descartado":
        return "descartado"
    if status not in STATUS_VALIDOS and status != "pendente":
        return f"status_{status}"
    if caso.get("duplicada_de"):
        return "duplicada"
    if caso.get("sem_resposta"):
        return None
    if status == "pendente" and not caso.get("trecho_confere", True):
        return "trecho_nao_confere"
    if caso.get("origem_ambigua"):
        return "origem_ambigua"
    return None


def _converter(caso: dict[str, Any]) -> dict[str, Any]:
    negativa = bool(caso.get("sem_resposta"))
    pergunta: dict[str, Any] = {
        "id": f"q{int(caso['id']):03d}",
        "pergunta": caso["pergunta"],
        "resposta_esperada": caso.get("resposta_esperada", ""),
        "fontes_aceitas": []
        if negativa
        else list(dict.fromkeys([caso["documento_origem"], *caso.get("documentos_aceitos", [])])),
        "dificuldade": caso.get("dificuldade"),
    }
    if not negativa:
        arquivo = caso.get("arquivo_origem") or caso["documento_origem"]
        pergunta["pasta"] = arquivo.split("/", 1)[0] if "/" in arquivo else ""
        pergunta["trecho"] = caso.get("trecho_origem", "")
    return pergunta


def carregar_dataset(
    caminho: Path = DATASET_CANONICO,
    *,
    incluir_pendentes: bool = False,
    auditoria: Path = AUDITORIA,
    dominio: str = DOMINIO_PADRAO,
) -> dict[str, Any]:
    """Devolve `{dominio, _pastas, perguntas, relatorio}` pronto para os runners."""
    bruto = json.loads(Path(caminho).read_text(encoding="utf-8"))
    cortes: Counter[str] = Counter()
    perguntas: list[dict[str, Any]] = []
    for caso in bruto["casos"]:
        motivo = _motivo_de_corte(caso, incluir_pendentes)
        if motivo:
            cortes[motivo] += 1
        else:
            perguntas.append(_converter(caso))

    if not perguntas:
        raise DatasetVazioError(
            f"nenhum caso passou nos cortes de {Path(caminho).name}: {dict(cortes)}. "
            "Revise o conjunto em /admin/datasets ou use --incluir-pendentes (ensaio)."
        )

    positivas = sum(1 for p in perguntas if p["fontes_aceitas"])
    return {
        "dominio": dominio,
        "_pastas": _pastas_do_corpus(auditoria),
        "perguntas": perguntas,
        "relatorio": {
            "total": len(bruto["casos"]),
            "usados": len(perguntas),
            "positivas": positivas,
            "negativas": len(perguntas) - positivas,
            "cortes": dict(cortes),
            "inclui_pendentes": incluir_pendentes,
        },
    }


def descrever(dataset: dict[str, Any]) -> str:
    """Uma linha para o log do runner, com o aviso de ensaio quando couber."""
    r = dataset["relatorio"]
    linha = (
        f"Dataset: {r['usados']}/{r['total']} casos "
        f"({r['positivas']} pos / {r['negativas']} neg); cortes: {r['cortes'] or '—'}"
    )
    if r["inclui_pendentes"]:
        linha += "\n  ATENÇÃO: inclui itens PENDENTES de revisão — ensaio, não vale como decisão."
    return linha


def rotulo_dataset(caminho: Path, incluir_pendentes: bool) -> str:
    """Nome gravado nos JSONs de resultado; separa ensaio de rodada oficial para
    que o `--retomar` por dataset não reaproveite pontos de um ensaio."""
    return Path(caminho).name + ("+pendentes" if incluir_pendentes else "")


def adicionar_argumentos(parser: Any) -> None:
    parser.add_argument("--dataset", type=Path, default=DATASET_CANONICO)
    parser.add_argument(
        "--incluir-pendentes",
        action="store_true",
        help="ensaio: inclui itens ainda não revisados (o resultado não vale como decisão)",
    )
