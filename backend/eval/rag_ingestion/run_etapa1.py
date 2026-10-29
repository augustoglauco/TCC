"""Etapa 1: harness de recuperação do RAG (Fase 10, R4 — `docs/EVALUATION.md`
Seção 2.1).

Mede **só recuperação** — `Recall@k`, `nDCG@10`, `MRR` e taxa de vazio —
sem gerar resposta e **sem nenhuma chamada de LLM-as-judge**. É o que torna
a varredura de parâmetros das Etapas 2–5 viável: uma configuração custa
~30 s em vez de uma chamada de juiz por pergunta e por ponto (que esbarra em
rate limit 429 do OpenRouter).

**Mede a busca crua (`QdrantRAGClient.search`), não o caminho do
orquestrador.** `_buscar_documentos_rag` acrescenta contexto da conversa e
um filtro que descarta documentos de outro produto — lógica que é idêntica
em todas as configurações comparadas e que, portanto, só adicionaria ruído
à escolha de `chunk_size`/modelo de embedding. O caminho de produção
completo volta a ser medido na Etapa 7, com LLM-as-judge, sobre a
configuração vencedora. Quem quiser a métrica do caminho de produção usa
`eval/rag_quality/run_eval.py`, que é para isso.

**O que ingerir sai da auditoria da Etapa 0**, não de uma lista fixa: só os
PDFs classificados como `util` em `auditoria_corpus.json`, mais `.md`/`.txt`.
Isso faz a decisão de 2026-10-17 (os 11 PDFs degenerados ficam de fora)
valer automaticamente, e faz o script falhar se a auditoria não tiver
rodado — em vez de medir silenciosamente um corpus diferente do auditado.

**Nunca toca na collection de produção.** Cada configuração cria uma
collection temporária com `purpose="admin"` e `is_active=False` (nunca
ativável nem buscável pelo chat público) e a apaga no `finally`, do Qdrant e
do Postgres.

Uso (a partir de `backend/`, com Qdrant e Postgres no ar):

    .venv/bin/python eval/rag_ingestion/run_etapa1.py
    .venv/bin/python eval/rag_ingestion/run_etapa1.py --chunk-size 512 --unidade tokens
    .venv/bin/python eval/rag_ingestion/run_etapa1.py --top-k 10 --score-threshold 0.25

Salva `eval/rag_ingestion/resultados_etapa1.json`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parents[1] / "src"))
sys.path.insert(0, str(BASE_DIR))

from dataset import (  # noqa: E402
    adicionar_argumentos,
    carregar_dataset,
    descrever,
    rotulo_dataset,
)
from metricas import (  # noqa: E402
    ResultadoPergunta,
    acerta_fonte,
    avaliar_conjunto,
    deduplicar_com_score,
)

from app.config import get_settings  # noqa: E402
from app.db.engine import create_db_engine, create_session_factory  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.rag.collections_registry import create_collection, delete_collection  # noqa: E402
from app.rag.embedders_registry import EmbedderRegistry  # noqa: E402
from app.rag.ingest import ingest_file  # noqa: E402
from app.rag.qdrant_client import QdrantRAGClient  # noqa: E402

logger = logging.getLogger(__name__)

RAIZ_REPO = BASE_DIR.parents[2]
CORPUS = RAIZ_REPO / "docs" / "Manuais_fornecedor" / "ControlId"
AUDITORIA = BASE_DIR / "auditoria_corpus.json"
SAIDA = BASE_DIR / "resultados_etapa1.json"

# Baseline de produção, para a primeira rodada do harness ser comparável ao
# que o sistema faz hoje. As Etapas 2 e 3 variam estes dois.
MODELO_PADRAO = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE_PADRAO = 800
CHUNK_OVERLAP_PADRAO = 100

# Mesmo perfil de HNSW do baseline. Não é varrido (Etapa 6): neste corpus o
# índice nunca é construído, a busca é exata — ver `docs/ARCHITECTURE.md`.
HNSW_PADRAO = {
    "hnsw_m": 16,
    "hnsw_ef_construct": 100,
    "hnsw_full_scan_threshold": 10000,
    "hnsw_max_indexing_threads": 0,
    "hnsw_on_disk": False,
    "hnsw_payload_m": None,
}

EXTENSOES_TEXTO = {".md", ".txt"}


class AuditoriaAusenteError(RuntimeError):
    """A Etapa 0 não rodou, ou rodou sobre outro corpus."""


def carregar_arquivos_a_ingerir(pastas: list[str]) -> list[Path]:
    """Lista os arquivos ingeríveis das `pastas`, segundo a auditoria.

    Só PDFs `util` entram — é assim que a decisão de deixar os 11 PDFs
    degenerados de fora vale sem lista manual. Arquivos `.md`/`.txt` entram
    direto (a auditoria os classifica em `itens_outros`, com `ingerivel`).
    """
    if not AUDITORIA.exists():
        raise AuditoriaAusenteError(
            f"{AUDITORIA.name} não existe. Rode a Etapa 0 primeiro:\n"
            "  .venv/bin/python eval/rag_ingestion/auditar_corpus.py"
        )
    auditoria = json.loads(AUDITORIA.read_text(encoding="utf-8"))
    if not auditoria.get("corpus", "").endswith("ControlId"):
        raise AuditoriaAusenteError(
            f"auditoria é de outro corpus ({auditoria.get('corpus')!r}); rode a Etapa 0 "
            "sobre docs/Manuais_fornecedor/ControlId"
        )

    escolhidos: list[Path] = []
    for item in auditoria["itens_pdfs"]:
        if item["classificacao"] == "util" and item["pasta"] in pastas:
            escolhidos.append(CORPUS / item["arquivo"])
    for item in auditoria["itens_outros"]:
        if item["pasta"] in pastas and item["extensao"] in EXTENSOES_TEXTO:
            escolhidos.append(CORPUS / item["arquivo"])

    faltando = [c for c in escolhidos if not c.exists()]
    if faltando:
        raise AuditoriaAusenteError(
            "auditoria aponta arquivos que não existem mais (rode a Etapa 0 de novo): "
            + ", ".join(str(f.relative_to(CORPUS)) for f in faltando[:5])
        )
    return sorted(escolhidos)


async def criar_collection_temporaria(
    *, session_factory, qdrant, embedder, arquivos, args, dimensao: int
):
    nome = f"eval_etapa1_{uuid.uuid4().hex[:8]}"
    async with session_factory() as session:
        collection = await create_collection(
            session,
            name=nome,
            embedding_model=args.embedding_model,
            vector_dimension=dimensao,
            distance_metric=args.distance,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            quantization_type="none",
            quantization_config={},
            payload_indexes=[],
            # purpose="admin" + is_active=False: nunca ativável nem buscável
            # pelo chat público (decisão de 2026-09-30).
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
                domain=args.dominio,
                session=session,
                origin="eval_etapa1",
            )
    return collection


async def apagar_collection(collection, qdrant, session_factory) -> None:
    await qdrant.drop_collection(collection.name)
    async with session_factory() as session:
        await delete_collection(session, collection.id)


async def medir(collection, qdrant, embedder, perguntas, args) -> tuple[list, list]:
    """Roda cada pergunta contra `collection` e devolve (resultados, detalhes)."""
    resultados: list[ResultadoPergunta] = []
    detalhes: list[dict] = []
    for caso in perguntas:
        documentos = await qdrant.search(
            collection.name,
            embedder,
            caso["pergunta"],
            args.dominio,
            top_k=args.top_k,
            score_threshold=args.score_threshold,
        )
        pares = deduplicar_com_score([(d.source, d.score) for d in documentos])
        fontes = [fonte for fonte, _ in pares]
        aceitas = set(caso["fontes_aceitas"])
        resultado = ResultadoPergunta(
            id=caso["id"],
            negativa=not aceitas,
            recuperadas=fontes,
            aceitas=aceitas,
        )
        resultados.append(resultado)
        detalhes.append(
            {
                "id": caso["id"],
                "pergunta": caso["pergunta"],
                "negativa": resultado.negativa,
                "fontes_aceitas": sorted(aceitas),
                # Pareado de propósito: a varredura offline de
                # `score_threshold` (Etapa 4) precisa do score com que cada
                # DOCUMENTO entrou. Guardar `fontes` e `scores` em listas
                # separadas desalinha as duas, porque 5 chunks recuperados
                # podem virar 3 fontes depois da deduplicação.
                "recuperadas": [
                    {"fonte": fonte, "score": round(score, 4)} for fonte, score in pares
                ],
                "score_maximo": round(pares[0][1], 4) if pares else None,
                "acertou": (
                    resultado.acertou_negativa
                    if resultado.negativa
                    else any(acerta_fonte(f, aceitas) for f in fontes)
                ),
            }
        )
    return resultados, detalhes


def _imprimir(metricas: dict, detalhes: list[dict], config: dict) -> None:
    print("\n=== Configuração ===")
    for chave, valor in config.items():
        print(f"  {chave:18s}: {valor}")

    print("\n=== Por pergunta ===")
    for d in detalhes:
        marca = "ok " if d["acertou"] else "ERR"
        tipo = "neg" if d["negativa"] else "pos"
        topo = ", ".join(r["fonte"] for r in d["recuperadas"][:3]) or "(vazio)"
        print(f"  [{marca}] {d['id']} {tipo} | {topo}")

    print("\n=== Métricas ===")
    print(
        f"  n: {metricas['n_total']} "
        f"({metricas['n_positivas']} pos / {metricas['n_negativas']} neg)"
    )
    for k, v in metricas["recall"].items():
        print(f"  Recall{k:4s}        : {v:.3f}" if v is not None else f"  Recall{k:4s}        : —")
    for rotulo, chave in (
        ("nDCG@10", "ndcg@10"),
        ("MRR", "mrr"),
        ("taxa vazio (pos)", "taxa_vazio_positivas"),
        ("acerto negativas", "acerto_negativas"),
    ):
        v = metricas[chave]
        print(f"  {rotulo:18s}: {v:.3f}" if v is not None else f"  {rotulo:18s}: —")


async def executar(args) -> int:
    dataset = carregar_dataset(args.dataset, incluir_pendentes=args.incluir_pendentes)
    print(descrever(dataset))
    perguntas = dataset["perguntas"]
    pastas = dataset["_pastas"]
    args.dominio = args.dominio or dataset["dominio"]

    arquivos = carregar_arquivos_a_ingerir(pastas)
    print(f"Corpus: {CORPUS.relative_to(RAIZ_REPO)}")
    print(f"Pastas: {', '.join(pastas)}")
    print(f"Arquivos a ingerir: {len(arquivos)}")
    for caminho in arquivos:
        print(f"  {caminho.relative_to(CORPUS)}")
    print(f"Perguntas: {len(perguntas)}")

    settings = get_settings()
    engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(engine)
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        # Fixo em False, de propósito, e NÃO lido de
        # `settings.rag_search_domain_fallback`: o fallback tenta de novo
        # sem o filtro de domínio quando a busca filtrada não acha nada,
        # ou seja, nunca devolve vazio. Isso destruiria a medição dos casos
        # negativos (cujo acerto É devolver vazio) e a `taxa_vazio_positivas`.
        # Se alguém ligar a flag no `.env`, o harness continua medindo a
        # mesma coisa.
        search_domain_fallback=False,
    )
    embedders = EmbedderRegistry()
    embedder = embedders.get(args.embedding_model)
    dimensao = await embedder.get_dimension()

    print(f"\nModelo: {args.embedding_model} ({dimensao} dims)")
    print(f"Criando collection temporária e ingerindo {len(arquivos)} arquivos...")
    collection = await criar_collection_temporaria(
        session_factory=session_factory,
        qdrant=qdrant,
        embedder=embedder,
        arquivos=arquivos,
        args=args,
        dimensao=dimensao,
    )
    try:
        resultados, detalhes = await medir(collection, qdrant, embedder, perguntas, args)
        metricas = avaliar_conjunto(resultados)
    finally:
        # Sempre limpa, mesmo se uma busca no meio falhar — nunca deixa
        # collection de teste órfã no Qdrant/Postgres.
        await apagar_collection(collection, qdrant, session_factory)
        await engine.dispose()

    config = {
        "embedding_model": args.embedding_model,
        "vector_dimension": dimensao,
        "distance_metric": args.distance,
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "top_k": args.top_k,
        "score_threshold": args.score_threshold,
        "dominio": args.dominio,
        "arquivos_ingeridos": len(arquivos),
    }
    _imprimir(metricas, detalhes, config)

    SAIDA.write_text(
        json.dumps(
            {
                "gerado_em": datetime.now(UTC).isoformat(),
                "dataset": rotulo_dataset(args.dataset, args.incluir_pendentes),
                "config": config,
                "metricas": metricas,
                "itens": detalhes,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nResultado: {SAIDA}")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Etapa 1 — métricas de recuperação do RAG")
    adicionar_argumentos(parser)
    parser.add_argument("--embedding-model", default=MODELO_PADRAO)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE_PADRAO)
    parser.add_argument("--chunk-overlap", type=int, default=CHUNK_OVERLAP_PADRAO)
    parser.add_argument(
        "--distance", default="cosine", choices=["cosine", "dot", "euclid", "manhattan"]
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--score-threshold", type=float, default=0.35)
    parser.add_argument("--dominio", default=None, help="padrão: o do dataset")
    args = parser.parse_args(argv[1:])

    if args.chunk_size <= args.chunk_overlap:
        parser.error("chunk_size deve ser maior que chunk_overlap")

    configure_logging()
    try:
        return asyncio.run(executar(args))
    except AuditoriaAusenteError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
