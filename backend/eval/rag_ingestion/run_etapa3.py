"""Etapa 3: grade 5×3 de `chunk_size` e `chunk_overlap` em tokens (Fase 10, R4 —
`docs/EVALUATION.md` Seção 2.1).

Com `app.rag.chunking.chunk_text` passando a contar **tokens** pelo tokenizer
do modelo da collection e a cortar recursivamente (`"\\n\\n"` → `"\\n"` →
`". "` → `" "`), este script varre a grade de 15 pontos sobre o modelo
escolhido na Etapa 2 (`google/embeddinggemma-300m` por padrão, janela de 2048
tokens):

- `chunk_size` ∈ {128, 256, 512, 768, 1024} tokens
- `chunk_overlap` ∈ {10%, 15%, 20%} de `chunk_size`

**Reaproveita a mesma instância de `TextEmbedder` nos 15 pontos** para pagar a
carga do modelo uma única vez, e é **retomável por ponto** (grava
`eval/rag_ingestion/resultados_etapa3.json` após cada configuração concluída).

**Nunca toca na collection de produção.** Cada ponto da grade cria uma
collection temporária (`purpose="admin"`, `is_active=False`) e a apaga no
`finally`, do Qdrant e do Postgres.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python eval/rag_ingestion/run_etapa3.py
    .venv/bin/python eval/rag_ingestion/run_etapa3.py --chunk-sizes 256 512 --overlaps-pct 15
    .venv/bin/python eval/rag_ingestion/run_etapa3.py --recalcular
"""

from __future__ import annotations

import argparse
import asyncio
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
from metricas import avaliar_conjunto  # noqa: E402
from run_etapa1 import (  # noqa: E402
    CORPUS,
    RAIZ_REPO,
    AuditoriaAusenteError,
    apagar_collection,
    carregar_arquivos_a_ingerir,
    criar_collection_temporaria,
    medir,
)
from run_etapa2 import ranquear_candidatos  # noqa: E402
from varrer_threshold import separabilidade  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.rag.embeddings import TextEmbedder  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

logger = logging.getLogger(__name__)

SAIDA = BASE_DIR / "resultados_etapa3.json"
MODELO_ETAPA3_PADRAO = "google/embeddinggemma-300m"
CHUNK_SIZES_TOKENS: tuple[int, ...] = (128, 256, 512, 768, 1024)
OVERLAPS_PCT: tuple[int, ...] = (10, 15, 20)
TOP_K_BASE = 10


@dataclass(frozen=True)
class PontoGradeChunking:
    """Um ponto `(chunk_size, overlap_pct)` da grade 5×3 da Etapa 3."""

    id: str
    chunk_size: int
    overlap_pct: int
    chunk_overlap: int


def gerar_grade() -> list[PontoGradeChunking]:
    """Gera os 15 pontos canônicos da grade 5×3 em tokens."""
    pontos: list[PontoGradeChunking] = []
    for cs in CHUNK_SIZES_TOKENS:
        for pct in OVERLAPS_PCT:
            ov = round(cs * (pct / 100))
            pontos.append(
                PontoGradeChunking(
                    id=f"cs{cs}_ov{pct}",
                    chunk_size=cs,
                    overlap_pct=pct,
                    chunk_overlap=ov,
                )
            )
    return pontos


def filtrar_grade(
    *,
    chunk_sizes: list[int] | None = None,
    overlaps_pct: list[int] | None = None,
) -> list[PontoGradeChunking]:
    """Filtra a grade 5×3 pelos `chunk_sizes` e/ou `overlaps_pct` pedidos."""
    if chunk_sizes:
        invalidos_cs = [c for c in chunk_sizes if c not in CHUNK_SIZES_TOKENS]
        if invalidos_cs:
            raise ValueError(
                f"chunk_size inválido: {invalidos_cs} (opções: {list(CHUNK_SIZES_TOKENS)})"
            )
    if overlaps_pct:
        invalidos_ov = [o for o in overlaps_pct if o not in OVERLAPS_PCT]
        if invalidos_ov:
            raise ValueError(f"overlap_pct inválido: {invalidos_ov} (opções: {list(OVERLAPS_PCT)})")
    cs_set = set(chunk_sizes) if chunk_sizes else set(CHUNK_SIZES_TOKENS)
    ov_set = set(overlaps_pct) if overlaps_pct else set(OVERLAPS_PCT)
    return [p for p in gerar_grade() if p.chunk_size in cs_set and p.overlap_pct in ov_set]


def _carregar_existentes(
    caminho: Path, dataset_nome: str, modelo: str, recalcular: bool
) -> dict[str, dict]:
    if recalcular or not caminho.exists():
        return {}
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    if dados.get("dataset") != dataset_nome or dados.get("embedding_model") != modelo:
        return {}
    return {item["id"]: item for item in dados.get("pontos", []) if "id" in item}


def _salvar_progresso(
    caminho: Path,
    dataset_nome: str,
    modelo: str,
    arquivos: list[Path],
    por_id: dict[str, dict],
) -> list[dict]:
    ordem = [p.id for p in gerar_grade() if p.id in por_id]
    lista = [por_id[pid] for pid in ordem]
    ranking = ranquear_candidatos(lista)
    vencedor = ranking[0] if ranking else None
    caminho.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(UTC).isoformat(),
                "dataset": dataset_nome,
                "embedding_model": modelo,
                "unidade_chunk": "tokens",
                "arquivos_ingeridos": len(arquivos),
                "vencedor": vencedor,
                "ranking": ranking,
                "pontos": lista,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ranking


def _imprimir_ranking(ranking: list[dict]) -> None:
    print("\n=== Ranking Etapa 3 (Grade 5×3 de Chunking em Tokens) ===")
    print(
        f"{'#':>2} {'Ponto':<14} {'nDCG@10':>8} {'R@5':>6} {'MRR':>6} "
        f"{'Sep?':>5} {'PosMin':>7} {'NegMax':>7} {'Ing(s)':>7}"
    )
    for r in ranking:
        sep_str = "SIM" if r["separavel"] else "NAO"
        pos_min = f"{r['menor_score_pos']:.3f}" if r["menor_score_pos"] is not None else "  —  "
        neg_max = f"{r['maior_score_neg']:.3f}" if r["maior_score_neg"] is not None else "  —  "
        print(
            f"{r['posicao']:>2} {r['id']:<14} "
            f"{r['ndcg@10']:>8.3f} {r['recall@5']:>6.3f} {r['mrr']:>6.3f} "
            f"{sep_str:>5} {pos_min:>7} {neg_max:>7} {r['tempo_ingestao_s']:>7.1f}"
        )


async def executar(args) -> int:
    pontos = filtrar_grade(chunk_sizes=args.chunk_sizes, overlaps_pct=args.overlaps_pct)
    dataset = carregar_dataset(args.dataset, incluir_pendentes=args.incluir_pendentes)
    print(descrever(dataset))
    perguntas = dataset["perguntas"]
    pastas = dataset["_pastas"]
    dominio = args.dominio or dataset["dominio"]

    arquivos = carregar_arquivos_a_ingerir(pastas)
    print(f"Corpus: {CORPUS.relative_to(RAIZ_REPO)}")
    print(
        f"Modelo: {args.embedding_model} | Pontos da grade: {len(pontos)} | "
        f"Arquivos: {len(arquivos)} | Perguntas: {len(perguntas)}"
    )

    por_id = _carregar_existentes(
        args.saida,
        rotulo_dataset(args.dataset, args.incluir_pendentes),
        args.embedding_model,
        args.recalcular,
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

    try:
        for ponto in pontos:
            if ponto.id in por_id and not args.recalcular:
                print(f"  [pulando {ponto.id}: já medido em {args.saida.name}]")
                continue

            args_ing = SimpleNamespace(
                embedding_model=args.embedding_model,
                distance=args.distance,
                chunk_size=ponto.chunk_size,
                chunk_overlap=ponto.chunk_overlap,
                dominio=dominio,
                top_k=TOP_K_BASE,
                score_threshold=0.0,
            )

            t0 = time.perf_counter()
            collection = await criar_collection_temporaria(
                session_factory=session_factory,
                qdrant=qdrant,
                embedder=embedder,
                arquivos=arquivos,
                args=args_ing,
                dimensao=dimensao,
            )
            tempo_ingestao_s = round(time.perf_counter() - t0, 2)

            try:
                resultados_crus, detalhes = await medir(
                    collection, qdrant, embedder, perguntas, args_ing
                )
                metricas_sem_corte = avaliar_conjunto(resultados_crus)
                sep = separabilidade(detalhes)
            finally:
                await apagar_collection(collection, qdrant, session_factory)

            print(
                f"  [{ponto.id}] ({ponto.chunk_size} tok / ov {ponto.chunk_overlap} tok = "
                f"{ponto.overlap_pct}%) -> R@5={metricas_sem_corte['recall']['@5']:.3f} | "
                f"nDCG@10={metricas_sem_corte['ndcg@10']:.3f} | "
                f"MRR={metricas_sem_corte['mrr']:.3f} | "
                f"sep={sep['separavel']} "
                f"({sep.get('menor_score_maximo_positivas')}/"
                f"{sep.get('maior_score_maximo_negativas')}) | "
                f"{tempo_ingestao_s:.1f}s"
            )

            por_id[ponto.id] = {
                "id": ponto.id,
                "embedding_model": args.embedding_model,
                "chunk_size": ponto.chunk_size,
                "overlap_pct": ponto.overlap_pct,
                "chunk_overlap": ponto.chunk_overlap,
                "unidade": "tokens",
                "tempo_ingestao_s": tempo_ingestao_s,
                "metricas_sem_corte": metricas_sem_corte,
                "separabilidade": sep,
                "itens": detalhes,
            }
            _salvar_progresso(
                args.saida,
                rotulo_dataset(args.dataset, args.incluir_pendentes),
                args.embedding_model,
                arquivos,
                por_id,
            )
    finally:
        await engine.dispose()

    ranking = _salvar_progresso(
        args.saida,
        rotulo_dataset(args.dataset, args.incluir_pendentes),
        args.embedding_model,
        arquivos,
        por_id,
    )
    _imprimir_ranking(ranking)
    print(f"\nResultado salvo em: {args.saida}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Etapa 3 — grade 5×3 de chunking em tokens")
    adicionar_argumentos(parser)
    parser.add_argument("--saida", type=Path, default=SAIDA)
    parser.add_argument("--embedding-model", default=MODELO_ETAPA3_PADRAO)
    parser.add_argument(
        "--chunk-sizes",
        type=int,
        nargs="+",
        default=None,
        help="Subconjunto de chunk_size em tokens (padrão: 128 256 512 768 1024)",
    )
    parser.add_argument(
        "--overlaps-pct",
        type=int,
        nargs="+",
        default=None,
        help="Subconjunto de overlaps em %% (padrão: 10 15 20)",
    )
    parser.add_argument(
        "--distance", default="cosine", choices=["cosine", "dot", "euclid", "manhattan"]
    )
    parser.add_argument("--dominio", default=None, help="padrão: o do dataset")
    parser.add_argument(
        "--recalcular",
        action="store_true",
        help="Reexecuta mesmo pontos já presentes no JSON de saída",
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
