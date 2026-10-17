"""Etapa 5: métrica de distância (`cosine` / `dot` / `euclid`) e payload index
`keyword` em `domain` (Fase 10, R4 — `docs/EVALUATION.md` Seção 2.1).

Executa duas baterias complementares sobre a configuração vencedora das Etapas
2–4 (`google/embeddinggemma-300m`, `chunk_size=512` tokens, `chunk_overlap=51`
tokens):

1. **Métricas de distância (`cosine`, `dot`, `euclid`):** para vetores
   normalizados (caso do `embeddinggemma-300m` e demais candidatos), `cosine`,
   `dot` e `euclid` produzem exatamente a mesma ordem de vizinhos — esta
   varredura registra a equivalência com números reais no corpus do TCC.
2. **Payload index `keyword` em `domain` (`sem_indice` vs
   `indice_domain_keyword`):** toda busca filtra por `domain`, mas o perfil
   inicial tinha `payload_indexes = []`. Mede `media_ms`, `p50_ms` e `p95_ms`
   tanto da consulta filtrada pura no Qdrant (`query_points` com vetores
   pré-calculados, isolando o custo do filtro no Qdrant da inferência da GPU)
   quanto da busca completa (`QdrantRAGClient.search`).

A combinação multi-tenant do Qdrant (`hnsw_m=0` + `hnsw_payload_m=16`) fica
fora de escopo (`docs/ROADMAP.md`): desabilita o grafo global e impede a busca
cross-domain usada quando o fallback está ativo.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python eval/rag_ingestion/run_etapa5.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from qdrant_client.models import FieldCondition, Filter, MatchValue

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parents[1] / "src"))
sys.path.insert(0, str(BASE_DIR))

from metricas import avaliar_conjunto  # noqa: E402
from run_etapa1 import (  # noqa: E402
    CORPUS,
    DATASET,
    HNSW_PADRAO,
    RAIZ_REPO,
    AuditoriaAusenteError,
    apagar_collection,
    carregar_arquivos_a_ingerir,
    medir,
)
from varrer_threshold import separabilidade  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.rag.collections_registry import create_collection  # noqa: E402
from app.rag.embeddings import TextEmbedder  # noqa: E402
from app.rag.ingest import ingest_file  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

logger = logging.getLogger(__name__)

SAIDA = BASE_DIR / "resultados_etapa5.json"
MODELO_PADRAO_ETAPA5 = "google/embeddinggemma-300m"
CHUNK_SIZE_PADRAO_ETAPA5 = 512
CHUNK_OVERLAP_PADRAO_ETAPA5 = 51
TOP_K_BASE = 10
REPETICOES_LATENCIA_PADRAO = 5

METRICAS_DISTANCIA: tuple[str, ...] = ("cosine", "dot", "euclid")
PERFIS_PAYLOAD_INDEX: dict[str, list[dict]] = {
    "sem_indice": [],
    "indice_domain_keyword": [{"field": "domain", "schema_type": "keyword"}],
}


def resumir_latencias_ms(amostras_ms: list[float]) -> dict:
    """Calcula `n`, `media_ms`, `p50_ms`, `p95_ms`, `min_ms` e `max_ms`."""
    if not amostras_ms:
        return {
            "n": 0,
            "media_ms": None,
            "p50_ms": None,
            "p95_ms": None,
            "min_ms": None,
            "max_ms": None,
        }
    ordenadas = sorted(amostras_ms)
    n = len(ordenadas)
    idx_p95 = min(n - 1, max(0, int(round(0.95 * n)) - 1))
    return {
        "n": n,
        "media_ms": round(statistics.fmean(ordenadas), 3),
        "p50_ms": round(statistics.median(ordenadas), 3),
        "p95_ms": round(ordenadas[idx_p95], 3),
        "min_ms": round(ordenadas[0], 3),
        "max_ms": round(ordenadas[-1], 3),
    }


def comparar_rankings_distancia(por_metrica: dict[str, dict]) -> dict:
    """Verifica se `cosine`, `dot` e `euclid` produziram exatamente o mesmo
    ranking por pergunta e as mesmas métricas agregadas."""
    if not por_metrica:
        return {"rankings_identicos": None}
    chaves = list(por_metrica.keys())
    ref = por_metrica[chaves[0]]
    fontes_ref = [[r["fonte"] for r in item["recuperadas"]] for item in ref.get("itens", [])]
    identicos = True
    for k in chaves[1:]:
        atual = por_metrica[k]
        fontes_atual = [
            [r["fonte"] for r in item["recuperadas"]] for item in atual.get("itens", [])
        ]
        if fontes_atual != fontes_ref:
            identicos = False
            break
    return {
        "metricas_comparadas": chaves,
        "rankings_identicos": identicos,
    }


async def _criar_collection_etapa5(
    *,
    session_factory,
    qdrant: QdrantRAGClient,
    embedder: TextEmbedder,
    arquivos: list[Path],
    embedding_model: str,
    dimensao: int,
    distance: str,
    chunk_size: int,
    chunk_overlap: int,
    dominio: str,
    payload_indexes: list[dict],
):
    nome = f"eval_etapa5_{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        collection = await create_collection(
            session,
            name=nome,
            embedding_model=embedding_model,
            vector_dimension=dimensao,
            distance_metric=distance,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            quantization_type="none",
            quantization_config={},
            payload_indexes=payload_indexes,
            purpose="admin",
            is_active=False,
            **HNSW_PADRAO,
        )
        for caminho in arquivos:
            await ingest_file(
                qdrant,
                embedder,
                collection,
                Path(get_settings().rag_uploads_dir),
                caminho,
                domain=dominio,
                session=session,
                origin="eval_etapa5",
            )
    return collection


async def _medir_latencia_qdrant_puro(
    qdrant: QdrantRAGClient,
    collection_name: str,
    vetores_consulta: list[list[float]],
    dominio: str,
    repeticoes: int,
) -> list[float]:
    filtro = Filter(must=[FieldCondition(key="domain", match=MatchValue(value=dominio))])
    # Warmup de 1 consulta para abrir conexão/cache.
    if vetores_consulta:
        await qdrant.async_client.query_points(
            collection_name=collection_name,
            query=vetores_consulta[0],
            query_filter=filtro,
            limit=TOP_K_BASE,
        )
    amostras_ms: list[float] = []
    for _ in range(repeticoes):
        for vetor in vetores_consulta:
            t0 = time.perf_counter()
            await qdrant.async_client.query_points(
                collection_name=collection_name,
                query=vetor,
                query_filter=filtro,
                limit=TOP_K_BASE,
            )
            amostras_ms.append((time.perf_counter() - t0) * 1000.0)
    return amostras_ms


async def executar(args) -> int:
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    perguntas = dataset["perguntas"]
    pastas = dataset["_pastas"]
    dominio = args.dominio or dataset["dominio"]
    arquivos = carregar_arquivos_a_ingerir(pastas)

    print(f"Corpus: {CORPUS.relative_to(RAIZ_REPO)}")
    print(
        f"Modelo: {args.embedding_model} | chunk={args.chunk_size}/{args.chunk_overlap} tok | "
        f"Arquivos: {len(arquivos)} | Perguntas: {len(perguntas)}"
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

    embedder = TextEmbedder(model_name=args.embedding_model)
    dimensao = await embedder.get_dimension()
    vetores_consulta = await embedder.embed([p["pergunta"] for p in perguntas], is_query=True)

    por_distancia: dict[str, dict] = {}
    por_payload_index: dict[str, dict] = {}

    try:
        print("\n=== Bateria 1: Métricas de distância (cosine / dot / euclid) ===")
        for dist in METRICAS_DISTANCIA:
            t0 = time.perf_counter()
            collection = await _criar_collection_etapa5(
                session_factory=session_factory,
                qdrant=qdrant,
                embedder=embedder,
                arquivos=arquivos,
                embedding_model=args.embedding_model,
                dimensao=dimensao,
                distance=dist,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                dominio=dominio,
                payload_indexes=PERFIS_PAYLOAD_INDEX["indice_domain_keyword"],
            )
            tempo_ing = round(time.perf_counter() - t0, 2)
            try:
                # No Qdrant, `score_threshold` é limite inferior (`score >= thr`)
                # para métricas de similaridade (`cosine`/`dot`), mas limite
                # SUPERIOR (`distancia <= thr`) para métricas de distância
                # (`euclid`/`manhattan`). Para vetores unitários (`||u - v|| <= 2`),
                # `thr=0.0` em `euclid` descartaria tudo que não tivesse distância 0;
                # `thr=10.0` desliga o corte em `euclid` da mesma forma que `0.0` em `cosine`.
                thr_sem_corte = 10.0 if dist in {"euclid", "manhattan"} else 0.0
                args_med = SimpleNamespace(
                    dominio=dominio, top_k=TOP_K_BASE, score_threshold=thr_sem_corte
                )
                resultados, detalhes = await medir(
                    collection, qdrant, embedder, perguntas, args_med
                )
                metricas = avaliar_conjunto(resultados)
                sep = separabilidade(detalhes)
            finally:
                await apagar_collection(collection, qdrant, session_factory)

            print(
                f"  [{dist:6s}] R@5={metricas['recall']['@5']:.3f} | "
                f"nDCG@10={metricas['ndcg@10']:.3f} | MRR={metricas['mrr']:.3f} | "
                f"sep={sep['separavel']} "
                f"({sep.get('menor_score_maximo_positivas')}/"
                f"{sep.get('maior_score_maximo_negativas')})"
            )
            por_distancia[dist] = {
                "distance_metric": dist,
                "tempo_ingestao_s": tempo_ing,
                "metricas_sem_corte": metricas,
                "separabilidade": sep,
                "itens": detalhes,
            }

        print("\n=== Bateria 2: Payload index keyword em domain (latência sob filtro) ===")
        for nome_perfil, payload_indexes in PERFIS_PAYLOAD_INDEX.items():
            collection = await _criar_collection_etapa5(
                session_factory=session_factory,
                qdrant=qdrant,
                embedder=embedder,
                arquivos=arquivos,
                embedding_model=args.embedding_model,
                dimensao=dimensao,
                distance="cosine",
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                dominio=dominio,
                payload_indexes=payload_indexes,
            )
            try:
                args_med = SimpleNamespace(dominio=dominio, top_k=TOP_K_BASE, score_threshold=0.0)
                t0_busca = time.perf_counter()
                resultados, _detalhes = await medir(
                    collection, qdrant, embedder, perguntas, args_med
                )
                tempo_busca_completa_ms = (
                    (time.perf_counter() - t0_busca) * 1000.0 / max(1, len(perguntas))
                )
                metricas = avaliar_conjunto(resultados)
                amostras_qdrant = await _medir_latencia_qdrant_puro(
                    qdrant,
                    collection.name,
                    vetores_consulta,
                    dominio,
                    args.repeticoes_latencia,
                )
                resumo_lat = resumir_latencias_ms(amostras_qdrant)
            finally:
                await apagar_collection(collection, qdrant, session_factory)

            print(
                f"  [{nome_perfil:22s}] Qdrant puro: média={resumo_lat['media_ms']:.2f}ms "
                f"p50={resumo_lat['p50_ms']:.2f}ms p95={resumo_lat['p95_ms']:.2f}ms "
                f"(n={resumo_lat['n']}) | R@5={metricas['recall']['@5']:.3f}"
            )
            por_payload_index[nome_perfil] = {
                "perfil": nome_perfil,
                "payload_indexes": payload_indexes,
                "latencia_qdrant_puro_ms": resumo_lat,
                "latencia_media_busca_completa_ms": round(tempo_busca_completa_ms, 2),
                "metricas_sem_corte": metricas,
            }
    finally:
        await engine.dispose()

    comp_dist = comparar_rankings_distancia(por_distancia)
    print(f"\nRankings idênticos entre cosine/dot/euclid? {comp_dist['rankings_identicos']}")

    args.saida.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(UTC).isoformat(),
                "dataset": args.dataset.name,
                "config_base": {
                    "embedding_model": args.embedding_model,
                    "vector_dimension": dimensao,
                    "chunk_size": args.chunk_size,
                    "chunk_overlap": args.chunk_overlap,
                    "unidade": "tokens",
                },
                "comparacao_distancias": comp_dist,
                "distancias": por_distancia,
                "payload_index_domain": por_payload_index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Resultado salvo em: {args.saida}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Etapa 5 — métrica de distância e payload index keyword em domain"
    )
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument("--embedding-model", default=MODELO_PADRAO_ETAPA5)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE_PADRAO_ETAPA5)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP_PADRAO_ETAPA5)
    parser.add_argument("--repeticoes-latencia", type=int, default=REPETICOES_LATENCIA_PADRAO)
    parser.add_argument("--dominio", default=None, help="padrão: o do dataset")
    args = parser.parse_args(argv[1:])

    configure_logging()
    try:
        return asyncio.run(executar(args))
    except AuditoriaAusenteError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
