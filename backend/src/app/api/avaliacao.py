"""Resultados da avaliação experimental (Fase 10) para a página pública
`/avaliacao`.

Lê os `results.json` versionados em `eval/` e devolve **só agregados**
(acurácia, matrizes, notas médias, latências, intervalos de confiança).
Respostas geradas, trechos de documentos recuperados e os textos dos ataques
de injeção NÃO saem daqui: a rota é pública, por decisão do dono do projeto
(`docs/ARCHITECTURE.md` §9), e os manuais do corpus podem ser material
protegido.

# MVP: sem cache nem limite de taxa — os dados são arquivos pequenos e
# estáticos; sem tabela nova.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger("assistente.avaliacao")

router = APIRouter(prefix="/api/avaliacao", tags=["Avaliação"])

_Z95 = 1.96


class Proporcao(BaseModel):
    """Proporção com intervalo de confiança de 95% (Wilson)."""

    acertos: int
    total: int
    taxa: float
    ic_inf: float
    ic_sup: float


class ResultadosAvaliacao(BaseModel):
    roteador: dict[str, Any] | None
    rag: dict[str, Any] | None
    chunk_size: dict[str, Any] | None
    etapa7: dict[str, Any] | None = None
    injecao: dict[str, Any] | None
    modelos: list[dict[str, Any]]


def intervalo_wilson(acertos: int, total: int) -> Proporcao:
    """Intervalo de Wilson para uma proporção. Com `total == 0` devolve zeros."""
    if total <= 0:
        return Proporcao(acertos=0, total=0, taxa=0.0, ic_inf=0.0, ic_sup=0.0)
    p = acertos / total
    z2 = _Z95**2
    centro = (p + z2 / (2 * total)) / (1 + z2 / total)
    margem = (_Z95 * math.sqrt(p * (1 - p) / total + z2 / (4 * total**2))) / (1 + z2 / total)
    return Proporcao(
        acertos=acertos,
        total=total,
        taxa=round(p, 4),
        ic_inf=round(max(0.0, centro - margem), 4),
        ic_sup=round(min(1.0, centro + margem), 4),
    )


def _ler_json(caminho: Path) -> Any | None:
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except OSError, json.JSONDecodeError:
        logger.warning("Resultado de avaliação ilegível: %s", caminho)
        return None


def _roteador(dados: dict | None) -> dict | None:
    if not dados or "providers" not in dados:
        return None
    provedores = []
    for nome, p in dados["providers"].items():
        prop = intervalo_wilson(int(p.get("acertos", 0)), int(p.get("total", 0)))
        provedores.append(
            {
                "provider": p.get("provider", nome),
                "acuracia": prop.model_dump(),
                "latencia_media_s": p.get("latencia_media_s"),
                "degradacoes": len(p.get("degradacoes_de_provider") or []),
                "matriz_confusao": p.get("matriz_confusao", {}),
            }
        )
    return {"dominios": dados.get("dominios", []), "provedores": provedores}


def _sem_resposta(dados: dict | None) -> dict:
    casos = (dados or {}).get("casos_sem_resposta") or []
    return {
        "total": len(casos),
        "recusou": sum(1 for c in casos if c.get("recusou")),
        "alucinou": sum(1 for c in casos if c.get("alucinou")),
    }


def _rag(dados: dict | None) -> dict | None:
    casos = (dados or {}).get("casos") or []
    if not casos:
        return None
    notas = [c["nota_llm_judge"]["nota"] for c in casos if c.get("nota_llm_judge")]
    fonte_ok = sum(1 for c in casos if c.get("fonte_correta"))
    por_dificuldade: dict[str, list[int]] = {}
    com_fonte: list[int] = []
    sem_fonte: list[int] = []
    for c in casos:
        nota = (c.get("nota_llm_judge") or {}).get("nota")
        if nota is None:
            continue
        por_dificuldade.setdefault(c.get("dificuldade", "n/d"), []).append(nota)
        (com_fonte if c.get("fonte_correta") else sem_fonte).append(nota)

    def media(xs: list[int]) -> float | None:
        return round(sum(xs) / len(xs), 3) if xs else None

    return {
        "sem_resposta": _sem_resposta(dados),
        "total": len(casos),
        "nota_media": media(notas),
        "fonte_correta": intervalo_wilson(fonte_ok, len(casos)).model_dump(),
        "nota_media_fonte_certa": media(com_fonte),
        "nota_media_fonte_errada": media(sem_fonte),
        "distribuicao_notas": {str(n): notas.count(n) for n in range(1, 6)},
        "por_dificuldade": [
            {"dificuldade": d, "total": len(v), "nota_media": media(v)}
            for d, v in por_dificuldade.items()
        ],
    }


def _chunk_size(dados: dict | None) -> dict | None:
    """Grade da Etapa 3 (`rag_ingestion/resultados_etapa3.json`): para cada
    `chunk_size` em tokens, o overlap de maior nDCG@10 (recuperação, sem juiz)."""
    pontos = (dados or {}).get("pontos")
    if not pontos:
        return None
    melhor_por_tamanho: dict[int, dict] = {}
    for p in pontos:
        m = p.get("metricas_sem_corte") or {}
        ponto = {
            "chunk_size": int(p["chunk_size"]),
            "overlap_pct": p.get("overlap_pct"),
            "ndcg_10": m.get("ndcg@10"),
            "recall_5": (m.get("recall") or {}).get("@5"),
        }
        atual = melhor_por_tamanho.get(ponto["chunk_size"])
        if atual is None or (ponto["ndcg_10"] or 0) > (atual["ndcg_10"] or 0):
            melhor_por_tamanho[ponto["chunk_size"]] = ponto
    lista = sorted(melhor_por_tamanho.values(), key=lambda x: x["chunk_size"])
    melhor = max(lista, key=lambda x: x["ndcg_10"] or 0)
    return {"pontos": lista, "melhor_chunk_size": melhor["chunk_size"]}


def _etapa7(dados: dict | None) -> dict | None:
    """Baseline x vencedora da Etapa 7 (`rag_quality/etapa7.json`, gerado por
    `consolidar_etapa7.py`): só agregados já calculados, sem respostas."""
    bracos = (dados or {}).get("bracos")
    if not bracos:
        return None
    for b in bracos:
        b["fonte_correta_ic"] = intervalo_wilson(
            int(b["fonte_correta"]), int(b["respondiveis"])
        ).model_dump()
    return {"bracos": bracos}


def _injecao(dados: dict | None) -> dict | None:
    if not dados:
        return None
    clientes = []
    for nome, c in dados.items():
        if not isinstance(c, dict) or "casos" not in c:
            continue
        por_categoria: dict[str, list[int]] = {}
        for caso in c["casos"]:
            cat = por_categoria.setdefault(caso.get("categoria", "n/d"), [0, 0])
            cat[0] += 1
            cat[1] += 1 if caso.get("comprometido") else 0
        total = int(c.get("total_casos", len(c["casos"])))
        comprometidos = int(c.get("comprometidos", 0))
        clientes.append(
            {
                "cliente": c.get("cliente", nome),
                "resistencia": intervalo_wilson(total - comprometidos, total).model_dump(),
                "por_categoria": [
                    {"categoria": k, "total": v[0], "comprometidos": v[1]}
                    for k, v in por_categoria.items()
                ],
            }
        )
    return {"clientes": clientes} if clientes else None


def _modelos(diretorio: Path) -> list[dict]:
    """Resultados do benchmark por modelo (`eval/model_benchmark/results/`).

    Envelope: `{versao, avaliacao, modelo, gerado_em, config, metricas,
    itens}`. Só `modelo`, `gerado_em`, `config` e `metricas` saem — `itens`
    (respostas) ficam de fora por a rota ser pública.
    """
    saida = []
    for arq in sorted(diretorio.glob("*.json")):
        d = _ler_json(arq)
        if isinstance(d, dict) and isinstance(d.get("metricas"), dict):
            saida.append(
                {
                    "modelo": d.get("modelo", arq.stem),
                    "gerado_em": d.get("gerado_em"),
                    "config": d.get("config", {}),
                    "metricas": d["metricas"],
                }
            )
    return saida


@router.get("/resultados", response_model=ResultadosAvaliacao)
async def obter_resultados() -> ResultadosAvaliacao:
    """Agregados das avaliações. Seção sem arquivo vem `null`/lista vazia —
    a página mostra "ainda não rodou" em vez de erro."""
    base = Path(get_settings().eval_dir).resolve()
    return ResultadosAvaliacao(
        roteador=_roteador(_ler_json(base / "router_intents" / "results.json")),
        rag=_rag(_ler_json(base / "rag_quality" / "results.json")),
        chunk_size=_chunk_size(_ler_json(base / "rag_ingestion" / "resultados_etapa3.json")),
        etapa7=_etapa7(_ler_json(base / "rag_quality" / "etapa7.json")),
        injecao=_injecao(_ler_json(base / "prompt_injection" / "results.json")),
        modelos=_modelos(base / "model_benchmark" / "results"),
    )
