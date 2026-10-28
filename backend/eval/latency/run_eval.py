"""Latência: modelo local x modelo externo (docs/EVALUATION.md, seção 3;
Fase 10, item 16 do roadmap).

Roda **os mesmos prompts** nos dois modelos: 60 mensagens do conjunto do
roteador (15 por domínio, amostra fixa pela seed), cada uma transformada no
prompt de produção por `_buscar_documentos_rag` + `_build_prompt`, com 3
repetições. O prompt é montado uma vez e reaproveitado — assim a diferença
medida é do modelo, não da recuperação. Uma chamada de aquecimento por
modelo é descartada (a primeira paga a carga na VRAM / a conexão).

Uso (a partir de `backend/`, Ollama e Qdrant no ar, `EXTERNAL_MODEL_API_KEY`
no `.env`; **GPU livre**, senão a latência local sai contaminada):

    .venv/bin/python eval/latency/run_eval.py --listar          # só mostra a amostra
    EXTERNAL_MODEL_NAME=anthropic/claude-haiku-5.5 \\
        .venv/bin/python eval/latency/run_eval.py

Opções: `--repeticoes N` (padrão 3), `--por-dominio N` (padrão 15), `--seed N`.
Grava `eval/latency/results.json`: por chamada (modelo, prompt, tempos,
tokens, custo) e resumo por modelo (média, mediana, p95, tokens, custo).
"""

import asyncio
import json
import random
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.orchestrator import _build_prompt, _buscar_documentos_rag

BASE_DIR = Path(__file__).parent
EVAL_DIR = BASE_DIR.parent
_DOMINIOS = ("vendas", "suporte", "atendimento", "agendamento")
# Mesmo contexto da avaliação de RAG: com top_k 5 o prompt passa de 4096 tokens.
_NUM_CTX_PADRAO = 8192


def _opcao(nome: str, padrao: str) -> str:
    return sys.argv[sys.argv.index(nome) + 1] if nome in sys.argv else padrao


def _amostra(por_dominio: int, seed: int) -> list[dict]:
    dados = json.loads((EVAL_DIR / "router_intents" / "dataset.json").read_text(encoding="utf-8"))
    validos = [
        c
        for c in dados["casos"]
        if not c.get("ambiguo") and (c.get("revisao") or {}).get("status") != "descartado"
    ]
    rng = random.Random(seed)
    saida: list[dict] = []
    for dominio in _DOMINIOS:
        do_dominio = sorted(
            (c for c in validos if c["intencao_esperada"] == dominio), key=lambda c: c["id"]
        )
        saida += rng.sample(do_dominio, min(por_dominio, len(do_dominio)))
    return saida


def percentil_95(valores: list[float]) -> float:
    ordenados = sorted(valores)
    k = 0.95 * (len(ordenados) - 1)
    i = int(k)
    j = min(i + 1, len(ordenados) - 1)
    return ordenados[i] * (1 - (k - i)) + ordenados[j] * (k - i)


def resumir(chamadas: list[dict]) -> dict:
    tempos = [c["total_s"] for c in chamadas]
    return {
        "chamadas": len(chamadas),
        "media_s": round(statistics.mean(tempos), 3),
        "mediana_s": round(statistics.median(tempos), 3),
        "p95_s": round(percentil_95(tempos), 3),
        "maximo_s": round(max(tempos), 3),
        "tokens_prompt_medio": round(statistics.mean(c["prompt_tokens"] or 0 for c in chamadas)),
        "tokens_saida_medio": round(statistics.mean(c["completion_tokens"] or 0 for c in chamadas)),
        "custo_total_usd": round(sum(c["custo_usd"] for c in chamadas), 5),
    }


async def _montar_prompts(settings, amostra: list[dict]) -> list[dict]:
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=settings.rag_search_domain_fallback,
    )
    session_factory = create_session_factory(create_db_engine(settings.postgres_dsn))
    rag = ActiveCollectionRagClient(qdrant, session_factory, EmbedderRegistry())
    prompts = []
    for caso in amostra:
        dominio = caso["intencao_esperada"]
        documentos = await _buscar_documentos_rag(
            caso["mensagem"], recent_messages=[], domain=dominio, rag_client=rag
        )
        prompts.append(
            {
                "id": caso["id"],
                "dominio": dominio,
                "prompt": _build_prompt(caso["mensagem"], documentos, domain=dominio),
            }
        )
    return prompts


async def _medir(nome: str, cliente, prompts: list[dict], repeticoes: int) -> list[dict]:
    await cliente.generate(prompts[0]["prompt"])  # aquecimento, descartado
    chamadas: list[dict] = []
    for rep in range(1, repeticoes + 1):
        for p in prompts:
            r = await cliente.generate(p["prompt"])
            chamadas.append(
                {
                    "modelo": nome,
                    "id": p["id"],
                    "dominio": p["dominio"],
                    "repeticao": rep,
                    "total_s": round(r.total_duration_ms / 1000, 3),
                    "carga_s": round((r.load_duration_ms or 0) / 1000, 3),
                    "prompt_eval_s": round((r.prompt_eval_duration_ms or 0) / 1000, 3),
                    "geracao_s": round((r.eval_duration_ms or 0) / 1000, 3),
                    "prompt_tokens": r.prompt_tokens,
                    "completion_tokens": r.completion_tokens,
                    "custo_usd": r.estimated_cost_usd,
                }
            )
        print(f"  {nome}: repetição {rep}/{repeticoes} concluída")
    return chamadas


def _clientes(settings) -> dict[str, object]:
    local = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=max(settings.local_llm_timeout_s, 180.0),
        temperature=settings.local_llm_temperature,
        num_ctx=settings.local_llm_num_ctx or _NUM_CTX_PADRAO,
        top_p=settings.local_llm_top_p,
        top_k=settings.local_llm_top_k,
        repeat_penalty=settings.local_llm_repeat_penalty,
        seed=settings.local_llm_seed,
    )
    externo = OpenRouterClient(
        base_url=settings.external_model_base_url,
        api_key=settings.external_model_api_key,
        model=settings.external_model_name,
        timeout_s=settings.external_llm_timeout_s,
        price_per_1k_input_tokens=settings.external_model_price_per_1k_input_tokens,
        price_per_1k_output_tokens=settings.external_model_price_per_1k_output_tokens,
        vision_model=settings.external_vision_model_name,
        jev_model=settings.jev_model_name,
        jev_timeout_s=settings.jev_timeout_s,
    )
    return {
        f"local:{settings.local_model_name}": local,
        f"externo:{settings.external_model_name}": externo,
    }


async def main() -> None:
    settings = get_settings()
    amostra = _amostra(int(_opcao("--por-dominio", "15")), int(_opcao("--seed", "42")))
    if "--listar" in sys.argv:
        print(f"{len(amostra)} mensagens; ids por domínio:")
        for d in _DOMINIOS:
            print(f"  {d}: {[c['id'] for c in amostra if c['intencao_esperada'] == d]}")
        return
    repeticoes = int(_opcao("--repeticoes", "3"))
    prompts = await _montar_prompts(settings, amostra)
    chamadas: list[dict] = []
    resumo: dict[str, dict] = {}
    for nome, cliente in _clientes(settings).items():
        print(f"=== {nome} ===")
        medidas = await _medir(nome, cliente, prompts, repeticoes)
        chamadas += medidas
        resumo[nome] = resumir(medidas)
        print(f"  {resumo[nome]}")
    saida = {
        "gerado_em": datetime.now(UTC).isoformat(),
        "repeticoes": repeticoes,
        "mensagens": len(prompts),
        "resumo": resumo,
        "chamadas": chamadas,
    }
    (BASE_DIR / "results.json").write_text(
        json.dumps(saida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("gravado em eval/latency/results.json")


if __name__ == "__main__":
    asyncio.run(main())
