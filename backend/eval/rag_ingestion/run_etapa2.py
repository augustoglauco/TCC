"""Etapa 2: escolha do modelo de embedding (Fase 10, R4 — `docs/EVALUATION.md`
Seção 2.1).

Compara os 4 candidatos do MTEB-BR sobre o corpus auditado (`ControlId/`),
respeitando a janela de tokens de cada modelo e aplicando os prefixos de
tarefa assimétricos (`query_prefix` vs `document_prefix` em
`app.rag.embeddings.TextEmbedder`):

1. `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, janela 128 tokens) —
   medido com `chunk_size=400` chars (~114 tokens) para não truncar metade do
   chunk como acontecia no baseline de 800 chars.
2. `google/embeddinggemma-300m` (768 dims, janela 2048 tokens, prefixos
   `"task: search result | query: "` e `"title: none | text: "`).
3. `intfloat/multilingual-e5-large-instruct` (1024 dims, janela 514 tokens,
   prefixos `"query: "` e `"passage: "`).
4. `BAAI/bge-m3` (1024 dims, janela 8192 tokens, sem prefixo).

**Retomável por candidato.** Grava `eval/rag_ingestion/resultados_etapa2.json`
a cada modelo concluído e pula candidatos já medidos (a menos que
`--recalcular` seja passado). Libera o modelo anterior da RAM/VRAM antes de
carregar o próximo, evitando acumular os 4 modelos em memória.

**Nunca toca na collection de produção.** Cada candidato cria uma collection
temporária (`purpose="admin"`, `is_active=False`) e a apaga no `finally`, do
Qdrant e do Postgres.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python eval/rag_ingestion/run_etapa2.py
    .venv/bin/python eval/rag_ingestion/run_etapa2.py --candidatos minilm-l12-v2 embeddinggemma-300m
    .venv/bin/python eval/rag_ingestion/run_etapa2.py --recalcular
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import logging
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parents[1] / "src"))
sys.path.insert(0, str(BASE_DIR))

from dataset import (  # noqa: E402
    adicionar_argumentos,
    carregar_dataset,
    descrever,
    rotulo_dataset,
)
from metricas import ResultadoPergunta, aplicar_threshold, avaliar_conjunto  # noqa: E402
from run_etapa1 import (  # noqa: E402
    CORPUS,
    RAIZ_REPO,
    AuditoriaAusenteError,
    apagar_collection,
    carregar_arquivos_a_ingerir,
    criar_collection_temporaria,
    medir,
)
from varrer_threshold import separabilidade  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.rag.embeddings import TextEmbedder, prefixos_do_modelo  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

logger = logging.getLogger(__name__)

SAIDA = BASE_DIR / "resultados_etapa2.json"
TOP_K_BASE = 10
THRESHOLD_PADRAO = 0.35
TOP_K_PADRAO = 5


@dataclass(frozen=True)
class CandidatoEmbedding:
    """Especificação de um candidato da Etapa 2."""

    id: str
    embedding_model: str
    dimensao_esperada: int
    janela_tokens: int
    chunk_size: int
    chunk_overlap: int
    notas: str


CANDIDATOS_ETAPA2: tuple[CandidatoEmbedding, ...] = (
    CandidatoEmbedding(
        id="minilm-l12-v2",
        embedding_model="paraphrase-multilingual-MiniLM-L12-v2",
        dimensao_esperada=384,
        janela_tokens=128,
        chunk_size=400,
        chunk_overlap=50,
        notas="Baseline corrigido para caber na janela de 128 tokens (~114 tokens a 3,5 chars/tok)",
    ),
    CandidatoEmbedding(
        id="embeddinggemma-300m",
        embedding_model="google/embeddinggemma-300m",
        dimensao_esperada=768,
        janela_tokens=2048,
        chunk_size=800,
        chunk_overlap=100,
        notas=(
            "1º MTEB-BR (Mean22 0,683) — prefixos "
            "'task: search result | query: ' e 'title: none | text: '"
        ),
    ),
    CandidatoEmbedding(
        id="e5-large-instruct",
        embedding_model="intfloat/multilingual-e5-large-instruct",
        dimensao_esperada=1024,
        janela_tokens=514,
        chunk_size=800,
        chunk_overlap=100,
        notas="2º MTEB-BR (Mean22 0,671) — prefixos 'query: ' e 'passage: '",
    ),
    CandidatoEmbedding(
        id="bge-m3",
        embedding_model="BAAI/bge-m3",
        dimensao_esperada=1024,
        janela_tokens=8192,
        chunk_size=800,
        chunk_overlap=100,
        notas="7º MTEB-BR (Mean22 0,625) — janela 8192 tokens, sem prefixo obrigatório",
    ),
)


def filtrar_candidatos(ids: list[str] | None) -> list[CandidatoEmbedding]:
    """Devolve todos os candidatos ou filtra pelos `ids` pedidos na ordem canônica."""
    if not ids:
        return list(CANDIDATOS_ETAPA2)
    conhecidos = {c.id: c for c in CANDIDATOS_ETAPA2}
    desconhecidos = [i for i in ids if i not in conhecidos]
    if desconhecidos:
        opcoes = ", ".join(conhecidos)
        raise ValueError(f"Candidato desconhecido: {', '.join(desconhecidos)} (opções: {opcoes})")
    escolhidos = set(ids)
    return [c for c in CANDIDATOS_ETAPA2 if c.id in escolhidos]


def ranquear_candidatos(resultados: list[dict]) -> list[dict]:
    """Ordena candidatos por Recall@5 desc, separabilidade desc, nDCG@10 desc,
    MRR desc e tempo de ingestão asc.

    No pipeline RAG, todos os chunks em `top_k=5` entram juntos no prompt do
    gerador, enquanto `score_threshold` é um corte duro que decide se o sistema
    responde ou recusa/escalona. Por isso recuperar a fonte no `top_k=5` e
    separar positivas de negativas vêm antes da posição fina dentro do top-5.
    """

    def chave(item: dict) -> tuple:
        m = item["metricas_sem_corte"]
        sep = bool(item.get("separabilidade", {}).get("separavel"))
        ndcg = m.get("ndcg@10") or 0.0
        recall5 = (m.get("recall") or {}).get("@5") or 0.0
        mrr = m.get("mrr") or 0.0
        tempo = item.get("tempo_ingestao_s") or float("inf")
        return (-round(recall5, 6), not sep, -round(ndcg, 6), -round(mrr, 6), round(tempo, 4))

    ordenados = sorted(resultados, key=chave)
    ranking: list[dict] = []
    for indice, item in enumerate(ordenados, start=1):
        m = item["metricas_sem_corte"]
        sep = item.get("separabilidade", {})
        ranking.append(
            {
                "posicao": indice,
                "id": item["id"],
                "embedding_model": item["embedding_model"],
                "ndcg@10": m.get("ndcg@10"),
                "recall@5": (m.get("recall") or {}).get("@5"),
                "mrr": m.get("mrr"),
                "separavel": sep.get("separavel"),
                "menor_score_pos": sep.get("menor_score_maximo_positivas"),
                "maior_score_neg": sep.get("maior_score_maximo_negativas"),
                "tempo_ingestao_s": item.get("tempo_ingestao_s"),
                "vram_alocada_mb": item.get("vram_alocada_mb"),
            }
        )
    return ranking


def _liberar_memoria() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats()
    except Exception:  # noqa: BLE001
        pass


def _vram_pico_mb() -> float | None:
    try:
        import torch

        if torch.cuda.is_available():
            return round(torch.cuda.max_memory_allocated() / (1024 * 1024), 1)
    except Exception:  # noqa: BLE001
        pass
    return None


def _avaliar_com_corte(detalhes: list[dict], threshold: float, top_k: int) -> dict:
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
        for item in detalhes
    ]
    return avaliar_conjunto(resultados)


async def _medir_candidato(
    candidato: CandidatoEmbedding,
    *,
    session_factory,
    qdrant: QdrantRAGClient,
    arquivos: list[Path],
    perguntas: list[dict],
    dominio: str,
    distance: str,
) -> dict:
    _liberar_memoria()
    embedder = TextEmbedder(model_name=candidato.embedding_model)
    prefixo_query, prefixo_doc = prefixos_do_modelo(candidato.embedding_model)

    t0_modelo = time.perf_counter()
    dimensao = await embedder.get_dimension()
    tempo_carga_s = round(time.perf_counter() - t0_modelo, 2)

    print(
        f"\n--- [{candidato.id}] {candidato.embedding_model} "
        f"({dimensao} dims, janela={candidato.janela_tokens} tok, "
        f"chunk={candidato.chunk_size}/{candidato.chunk_overlap}) ---"
    )
    if prefixo_query or prefixo_doc:
        print(f"  Prefixos: query={prefixo_query!r} | doc={prefixo_doc!r}")

    args_ing = SimpleNamespace(
        embedding_model=candidato.embedding_model,
        distance=distance,
        chunk_size=candidato.chunk_size,
        chunk_overlap=candidato.chunk_overlap,
        dominio=dominio,
        top_k=TOP_K_BASE,
        score_threshold=0.0,
    )

    t0_ingestao = time.perf_counter()
    collection = await criar_collection_temporaria(
        session_factory=session_factory,
        qdrant=qdrant,
        embedder=embedder,
        arquivos=arquivos,
        args=args_ing,
        dimensao=dimensao,
    )
    tempo_ingestao_s = round(time.perf_counter() - t0_ingestao, 2)

    try:
        t0_busca = time.perf_counter()
        resultados_crus, detalhes = await medir(collection, qdrant, embedder, perguntas, args_ing)
        tempo_busca_s = round(time.perf_counter() - t0_busca, 2)
        metricas_sem_corte = avaliar_conjunto(resultados_crus)
        metricas_thr_padrao = _avaliar_com_corte(detalhes, THRESHOLD_PADRAO, TOP_K_PADRAO)
        sep = separabilidade(detalhes)
        vram_mb = _vram_pico_mb()
    finally:
        await apagar_collection(collection, qdrant, session_factory)
        del embedder
        _liberar_memoria()

    print(
        f"  R@5={metricas_sem_corte['recall']['@5']:.3f} | "
        f"nDCG@10={metricas_sem_corte['ndcg@10']:.3f} | "
        f"MRR={metricas_sem_corte['mrr']:.3f} | "
        f"separável={sep['separavel']} "
        f"(pos_min={sep.get('menor_score_maximo_positivas')}, "
        f"neg_max={sep.get('maior_score_maximo_negativas')}) | "
        f"ingestão={tempo_ingestao_s:.1f}s"
    )

    return {
        "id": candidato.id,
        "embedding_model": candidato.embedding_model,
        "vector_dimension": dimensao,
        "janela_tokens": candidato.janela_tokens,
        "chunk_size": candidato.chunk_size,
        "chunk_overlap": candidato.chunk_overlap,
        "distance_metric": distance,
        "prefixo_query": prefixo_query,
        "prefixo_documento": prefixo_doc,
        "notas": candidato.notas,
        "tempo_carga_modelo_s": tempo_carga_s,
        "tempo_ingestao_s": tempo_ingestao_s,
        "tempo_busca_s": tempo_busca_s,
        "vram_alocada_mb": vram_mb,
        "metricas_sem_corte": metricas_sem_corte,
        "metricas_threshold_035": metricas_thr_padrao,
        "separabilidade": sep,
        "itens": detalhes,
    }


def _imprimir_ranking(ranking: list[dict]) -> None:
    print("\n=== Ranking Etapa 2 (Modelos de Embedding) ===")
    print(
        f"{'#':>2} {'Candidato':<20} {'nDCG@10':>8} {'R@5':>6} {'MRR':>6} "
        f"{'Sep?':>5} {'PosMin':>7} {'NegMax':>7} {'Ing(s)':>7}"
    )
    for r in ranking:
        sep_str = "SIM" if r["separavel"] else "NAO"
        pos_min = f"{r['menor_score_pos']:.3f}" if r["menor_score_pos"] is not None else "  —  "
        neg_max = f"{r['maior_score_neg']:.3f}" if r["maior_score_neg"] is not None else "  —  "
        print(
            f"{r['posicao']:>2} {r['id']:<20} "
            f"{r['ndcg@10']:>8.3f} {r['recall@5']:>6.3f} {r['mrr']:>6.3f} "
            f"{sep_str:>5} {pos_min:>7} {neg_max:>7} {r['tempo_ingestao_s']:>7.1f}"
        )


def _carregar_existentes(caminho: Path, dataset_nome: str, recalcular: bool) -> dict[str, dict]:
    if recalcular or not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    if dados.get("dataset") != dataset_nome:
        return {}
    return {item["id"]: item for item in dados.get("candidatos", []) if "id" in item}


def _salvar_progresso(
    caminho: Path, dataset_nome: str, arquivos: list[Path], por_id: dict[str, dict]
) -> list[dict]:
    ordem_ids = [c.id for c in CANDIDATOS_ETAPA2 if c.id in por_id]
    lista = [por_id[cid] for cid in ordem_ids]
    ranking = ranquear_candidatos(lista)
    vencedor = ranking[0] if ranking else None
    caminho.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(UTC).isoformat(),
                "dataset": dataset_nome,
                "arquivos_ingeridos": len(arquivos),
                "vencedor": vencedor,
                "ranking": ranking,
                "candidatos": lista,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ranking


async def executar(args) -> int:
    candidatos = filtrar_candidatos(args.candidatos)
    dataset = carregar_dataset(args.dataset, incluir_pendentes=args.incluir_pendentes)
    print(descrever(dataset))
    perguntas = dataset["perguntas"]
    pastas = dataset["_pastas"]
    dominio = args.dominio or dataset["dominio"]

    arquivos = carregar_arquivos_a_ingerir(pastas)
    print(f"Corpus: {CORPUS.relative_to(RAIZ_REPO)}")
    print(f"Arquivos a ingerir: {len(arquivos)} | Perguntas: {len(perguntas)}")

    por_id = _carregar_existentes(
        args.saida, rotulo_dataset(args.dataset, args.incluir_pendentes), args.recalcular
    )

    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(engine)
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=False,
    )

    try:
        for candidato in candidatos:
            if candidato.id in por_id and not args.recalcular:
                print(f"\n[pulando {candidato.id}: já medido em {args.saida.name}]")
                continue
            resultado = await _medir_candidato(
                candidato,
                session_factory=session_factory,
                qdrant=qdrant,
                arquivos=arquivos,
                perguntas=perguntas,
                dominio=dominio,
                distance=args.distance,
            )
            por_id[candidato.id] = resultado
            _salvar_progresso(
                args.saida, rotulo_dataset(args.dataset, args.incluir_pendentes), arquivos, por_id
            )
    finally:
        await engine.dispose()

    ranking = _salvar_progresso(
        args.saida, rotulo_dataset(args.dataset, args.incluir_pendentes), arquivos, por_id
    )
    _imprimir_ranking(ranking)
    print(f"\nResultado salvo em: {args.saida}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Etapa 2 — escolha do modelo de embedding")
    adicionar_argumentos(parser)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument(
        "--candidatos",
        nargs="+",
        default=None,
        help="IDs dos candidatos a rodar (padrão: todos os 4)",
    )
    parser.add_argument(
        "--distance", default="cosine", choices=["cosine", "dot", "euclid", "manhattan"]
    )
    parser.add_argument("--dominio", default=None, help="padrão: o do dataset")
    parser.add_argument(
        "--recalcular",
        action="store_true",
        help="Reexecuta mesmo candidatos já presentes no JSON de saída",
    )
    args = parser.parse_args(argv[1:])

    configure_logging()
    try:
        return asyncio.run(executar(args))
    except (AuditoriaAusenteError, ValueError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
