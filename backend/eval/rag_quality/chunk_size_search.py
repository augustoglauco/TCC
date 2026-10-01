"""Busca por bisseção do `chunk_size` que maximiza a qualidade do RAG (R4,
Fase 10) — complementa `run_eval.py` (que mede a collection ATIVA de
produção, `chunk_size=800`) testando outros valores sem nunca tocar nela.

Mecânica: para cada `chunk_size` candidato, cria uma collection TEMPORÁRIA
(`chunk_overlap` = 12,5% de `chunk_size`, mesma proporção do baseline de
produção 100/800), reingere só os 11 PDFs reais do domínio Suporte
(`docs/Manuais_fornecedor/` + `ControlId/` — os únicos relevantes às 18
perguntas de `dataset.json`, já que a busca sempre filtra por
`domain="suporte"`), roda a mesma suíte de 18 perguntas contra ela
(reaproveitando `_julgar_resposta`/`_fonte_e_correta` de `run_eval.py` e
`_build_prompt`/`_buscar_documentos_rag` do orchestrator), mede nota
média + taxa de fonte correta, e **sempre apaga a collection temporária**
ao final (Qdrant + arquivos + Postgres), nunca deixando lixo.

Bisseção: começa nos extremos de uma sequência comum de duplicação (200 e
1600 caracteres) e compara contra o baseline de produção já medido em 800
(`eval/rag_quality/results.json`, não precisa remedir) — fica com a metade
que melhorou, prova o novo ponto médio dela, repete até o range cair abaixo
de `_PASSO_MINIMO` ou `_MAX_RODADAS` ser atingido. Com só 18 perguntas e uma
nota de LLM-as-judge ruidosa, isto indica uma REGIÃO razoável, não um ótimo
exato — todos os pontos medidos ficam no relatório final, não só o
"vencedor" (ver docs/ROADMAP.md Fase 10 para a decisão de usar bisseção em
vez de grade completa).

Uso (a partir de `backend/`, com Ollama, Qdrant e Postgres reais no ar e
`EXTERNAL_MODEL_API_KEY` configurada no `.env`):

    .venv/bin/python eval/rag_quality/chunk_size_search.py

Salva `eval/rag_quality/chunk_size_search_results.json`.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from statistics import mean

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.rag.collections_registry import create_collection, delete_collection
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.ingest import ingest_file
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.orchestrator import _build_prompt, _buscar_documentos_rag

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
from run_eval import _carregar_casos, _fonte_e_correta, _julgar_resposta  # noqa: E402

_DOMAIN = "suporte"
_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_VECTOR_DIMENSION = 384
_PROPORCAO_OVERLAP = 0.125  # mesma proporção do baseline de produção (100/800)
_PASSO_MINIMO = 100  # para de bisseccionar quando o range já é menor que isto
_MAX_RODADAS = 5

# Os 11 PDFs reais do domínio Suporte referenciados pelas 18 perguntas de
# dataset.json — únicos pertinentes, já que a busca sempre filtra por
# domain="suporte" (os outros 37 documentos da collection de produção são de
# outros domínios/categorias e nunca entrariam no resultado desta avaliação).
_MANUAIS_FORNECEDOR = Path("/home/augusto/Projetos/TCC/docs/Manuais_fornecedor")
_PDFS_SUPORTE = [
    _MANUAIS_FORNECEDOR / "Datasheet - iNVU 9164 M2 IAX FT.pdf",
    _MANUAIS_FORNECEDOR / "Datasheet 7550 BD Z IA  FT - V018_0.pdf",
    _MANUAIS_FORNECEDOR / "Manual VIP 5200 (D) TM FT_0.pdf",
    _MANUAIS_FORNECEDOR / "Manual VIP 7415 DUAL IA FT.pdf",
    _MANUAIS_FORNECEDOR / "Manual_IP_Utility_01-26_site_4.pdf",
    _MANUAIS_FORNECEDOR / "Manual_MHDX_1104_1108_1116C_01-26_site.pdf",
    _MANUAIS_FORNECEDOR / "Manual_V3001_01-26_site.pdf",
    _MANUAIS_FORNECEDOR / "Manual_iNVD1016_01-26_site_0.pdf",
    _MANUAIS_FORNECEDOR / "Tabela_comparativa_gravadores_2025.pdf",
    _MANUAIS_FORNECEDOR / "ControlId" / "idbell-datasheet-pt.pdf",
    _MANUAIS_FORNECEDOR / "ControlId" / "rep-idclass-manual.pdf",
]

_DEFAULT_HNSW = dict(
    hnsw_m=16,
    hnsw_ef_construct=100,
    hnsw_full_scan_threshold=10000,
    hnsw_max_indexing_threads=0,
    hnsw_on_disk=False,
    hnsw_payload_m=None,
)


class _FixedCollectionRagClient:
    """Implementa o Protocol `RAGClient` apontando para UMA collection fixa
    pelo nome, em vez da collection ativa (`ActiveCollectionRagClient`) —
    permite reaproveitar `_buscar_documentos_rag` sem nunca tocar na
    collection de produção."""

    def __init__(self, qdrant: QdrantRAGClient, collection_name: str, embedder) -> None:
        self._qdrant = qdrant
        self._collection_name = collection_name
        self._embedder = embedder

    async def search(self, query: str, domain: str, top_k: int = 3, score_threshold: float = 0.35):
        return await self._qdrant.search(
            self._collection_name,
            self._embedder,
            query,
            domain,
            top_k=top_k,
            score_threshold=score_threshold,
        )


async def _criar_e_popular_collection(
    chunk_size: int, qdrant, embedders, session_factory, uploads_dir: Path
):
    chunk_overlap = max(1, round(chunk_size * _PROPORCAO_OVERLAP))
    nome = f"eval_chunk_search_{chunk_size}_{uuid.uuid4().hex[:8]}"
    embedder = embedders.get(_EMBEDDING_MODEL)

    async with session_factory() as session:
        collection = await create_collection(
            session,
            name=nome,
            embedding_model=_EMBEDDING_MODEL,
            vector_dimension=_VECTOR_DIMENSION,
            distance_metric="cosine",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            quantization_type="none",
            quantization_config={},
            payload_indexes=[],
            purpose="admin",  # nunca ativável/buscável pelo chat público (decisão de 2026-09-30)
            is_active=False,
            **_DEFAULT_HNSW,
        )
        for caminho in _PDFS_SUPORTE:
            await ingest_file(
                qdrant,
                embedder,
                collection,
                uploads_dir,
                caminho,
                domain=_DOMAIN,
                session=session,
                origin="eval_chunk_size_search",
            )
    return collection


async def _apagar_collection(collection, qdrant, session_factory) -> None:
    await qdrant.drop_collection(collection.name)
    async with session_factory() as session:
        await delete_collection(session, collection.id)


async def _avaliar_chunk_size(
    chunk_size: int,
    casos,
    qdrant,
    embedders,
    session_factory,
    uploads_dir,
    local_client,
    judge_client,
) -> dict:
    print(f"\n=== chunk_size={chunk_size} (overlap={round(chunk_size * _PROPORCAO_OVERLAP)}) ===")
    collection = await _criar_e_popular_collection(
        chunk_size, qdrant, embedders, session_factory, uploads_dir
    )
    embedder = embedders.get(_EMBEDDING_MODEL)
    rag_client = _FixedCollectionRagClient(qdrant, collection.name, embedder)

    resultados_casos = []
    try:
        for caso in casos:
            documentos = await _buscar_documentos_rag(
                caso["pergunta"], recent_messages=[], domain=_DOMAIN, rag_client=rag_client
            )
            prompt = _build_prompt(caso["pergunta"], documentos, domain=_DOMAIN)
            resposta_llm = await local_client.generate(prompt)
            fontes = [documento.source for documento in documentos]
            fonte_correta = _fonte_e_correta(fontes, caso["documento_origem"])
            julgamento = await _julgar_resposta(
                judge_client, caso["pergunta"], caso["resposta_esperada"], resposta_llm.text, fontes
            )
            resultados_casos.append(
                {"id": caso["id"], "fonte_correta": fonte_correta, "nota": julgamento.get("nota")}
            )
            print(f"  [{caso['id']}] fonte_correta={fonte_correta} nota={julgamento.get('nota')}")
    finally:
        # Sempre limpa, mesmo se uma chamada no meio falhar — nunca deixa
        # collection de teste órfã no Qdrant/Postgres.
        await _apagar_collection(collection, qdrant, session_factory)

    notas = [c["nota"] for c in resultados_casos if isinstance(c["nota"], (int, float))]
    return {
        "chunk_size": chunk_size,
        "chunk_overlap": round(chunk_size * _PROPORCAO_OVERLAP),
        "nota_media": round(mean(notas), 3) if notas else None,
        "fonte_correta_taxa": round(
            sum(1 for c in resultados_casos if c["fonte_correta"]) / len(resultados_casos), 3
        ),
        "casos": resultados_casos,
    }


async def main() -> None:
    settings = get_settings()
    casos = _carregar_casos()

    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=settings.rag_search_domain_fallback,
    )
    embedders = EmbedderRegistry()
    db_engine = create_db_engine(settings.postgres_dsn)
    session_factory = create_session_factory(db_engine)
    uploads_dir = Path(settings.rag_uploads_dir)

    local_client = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=settings.local_llm_timeout_s,
        temperature=settings.local_llm_temperature,
        num_ctx=settings.local_llm_num_ctx,
        top_p=settings.local_llm_top_p,
        top_k=settings.local_llm_top_k,
        repeat_penalty=settings.local_llm_repeat_penalty,
        seed=settings.local_llm_seed,
    )
    judge_client = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
    )

    # Baseline de produção (chunk_size=800) já medido em
    # eval/rag_quality/results.json — não remede, só reaproveita.
    baseline = json.loads((BASE_DIR / "results.json").read_text(encoding="utf-8"))
    notas_baseline = [c["nota_llm_judge"].get("nota") for c in baseline["casos"]]
    pontos: dict[int, dict] = {
        800: {
            "chunk_size": 800,
            "chunk_overlap": 100,
            "nota_media": round(mean(notas_baseline), 3),
            "fonte_correta_taxa": round(
                sum(1 for c in baseline["casos"] if c["fonte_correta"]) / len(baseline["casos"]), 3
            ),
            "origem": "baseline de produção (results.json), não remedido",
        }
    }
    print(f"Baseline conhecido: chunk_size=800 -> nota={pontos[800]['nota_media']}")

    low, high = 200, 1600
    for rodada in range(_MAX_RODADAS):
        for candidato in (low, high):
            if candidato not in pontos:
                pontos[candidato] = await _avaliar_chunk_size(
                    candidato,
                    casos,
                    qdrant,
                    embedders,
                    session_factory,
                    uploads_dir,
                    local_client,
                    judge_client,
                )

        score = lambda cs: pontos[cs]["nota_media"]  # noqa: E731
        melhor = max(low, high, 800, key=score)
        print(
            f"\nRodada {rodada + 1}: low={low}(nota={score(low)}) high={high}(nota={score(high)}) "
            f"baseline=800(nota={score(800)}) -> melhor={melhor}"
        )

        if high - low < _PASSO_MINIMO:
            break

        meio = (low + high) // 2
        if melhor == low:
            high = meio
        elif melhor == high:
            low = meio
        else:
            # 800 (ou o meio corrente) venceu dos dois lados — estreita a
            # busca em torno dele em vez de continuar nas pontas antigas.
            low, high = max(200, melhor - (high - low) // 4), min(1600, melhor + (high - low) // 4)

    resultado_final = {
        "pontos_medidos": dict(sorted(pontos.items())),
        "melhor_chunk_size": max(pontos, key=lambda cs: pontos[cs]["nota_media"]),
    }
    output_path = BASE_DIR / "chunk_size_search_results.json"
    output_path.write_text(
        json.dumps(resultado_final, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nMelhor chunk_size encontrado: {resultado_final['melhor_chunk_size']}")
    print(f"Resultados salvos em {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
