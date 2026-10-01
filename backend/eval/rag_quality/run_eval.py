"""Avalia a qualidade das respostas do RAG (R4, Fase 10) sobre o conjunto de
referência em `dataset.json` — ver docs/EVALUATION.md Seção 2.

Reproduz o caminho real de produção para o domínio "suporte" (busca RAG via
`_buscar_documentos_rag` + prompt via `_build_prompt` + geração pelo modelo
local), sem passar pelo classificador de intenção — a acurácia do roteador
já é avaliada separadamente em `eval/router_intents/`; aqui o domínio é
fixado em "suporte" de propósito (onde os manuais/datasheets estão
indexados no RAG), para isolar a qualidade da recuperação/geração do efeito
de uma classificação de intenção errada.

Usa um LLM-as-judge (modelo EXTERNO, diferente do gerador local, para
reduzir o viés de "o modelo se autoavalia bem") comparando a resposta
gerada com o gabarito — prompt novo, documentado em
docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md. A nota manual (1-5,
docs/EVALUATION.md) fica `null` de propósito para o desenvolvedor/orientador
preencher à mão depois: ao contrário da nota do LLM-as-judge, exige
julgamento humano de verdade — um LLM "avaliando manualmente" seria só um
segundo juiz automático disfarçado, não a segunda fonte de sinal
independente que o documento pede.

Uso (a partir de `backend/`, com Ollama, Qdrant e Postgres reais no ar, a
collection `docs_texto` ativa e populada com os manuais, e
`EXTERNAL_MODEL_API_KEY` configurada no `.env` para o LLM-as-judge):

    .venv/bin/python eval/rag_quality/run_eval.py

Salva `eval/rag_quality/results.json`.
"""

import asyncio
import json
import re
from pathlib import Path

import httpx

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.classifier import strip_code_fence
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.orchestrator import _build_prompt, _buscar_documentos_rag

BASE_DIR = Path(__file__).parent
_DOMAIN = "suporte"

# Prompt novo (LLM-as-judge) — ver docs/Manuais/PROMPTS_E_INSTRUCOES_LLM.md.
# Critérios pedidos por docs/EVALUATION.md Seção 2: relevância, correção
# factual, uso da fonte recuperada. Modelo EXTERNO (diferente do gerador
# local) para reduzir viés de autoavaliação.
_JUDGE_PROMPT_TEMPLATE = """\
Você é um avaliador técnico imparcial. Compare a resposta gerada por um \
assistente de IA com a resposta esperada (gabarito) para a mesma pergunta \
técnica sobre equipamentos, e dê notas de 1 (péssima) a 5 (excelente).

Critérios:
- "relevancia": a resposta gerada realmente responde ao que foi perguntado?
- "correcao_factual": as informações batem com o gabarito (números, nomes, \
limites técnicos)? Penalize alucinações (dados inventados que não estão no \
gabarito nem nas fontes recuperadas).
- "uso_fonte": a resposta se apoia no conteúdo das fontes recuperadas \
abaixo, em vez de conhecimento genérico não verificável?
- "nota": nota geral de qualidade, considerando os três critérios acima.

Pergunta: {pergunta}

Resposta esperada (gabarito): {resposta_esperada}

Fontes recuperadas pelo RAG (o que o assistente tinha disponível para responder):
{fontes}

Resposta gerada pelo assistente: {resposta_gerada}

Responda APENAS com JSON no formato: {{"nota": <1 a 5>, "relevancia": <1 a 5>, \
"correcao_factual": <1 a 5>, "uso_fonte": <1 a 5>, "justificativa": "<1-2 frases>"}}."""


def _carregar_casos() -> list[dict]:
    dados = json.loads((BASE_DIR / "dataset.json").read_text(encoding="utf-8"))
    return dados["casos"]


def _normalizar_nome_arquivo(nome: str) -> str:
    # Achado ao rodar esta avaliação: um dos PDFs enviados por upload tem
    # espaço duplo no nome real do arquivo ("...IA  FT..."), diferente do
    # nome usado no gabarito (`dataset.json`) — comparação ingênua marcava
    # falso negativo em "fonte_correta" mesmo quando o documento certo foi
    # de fato recuperado. Colapsa espaços antes de comparar.
    return re.sub(r"\s+", " ", nome.lower()).strip()


def _fonte_e_correta(fontes: list[str], documento_origem: str) -> bool:
    origem = _normalizar_nome_arquivo(documento_origem)
    return any(origem in _normalizar_nome_arquivo(fonte) for fonte in fontes)


_MAX_TENTATIVAS_JUIZ = 4


async def _julgar_resposta(
    judge_client, pergunta: str, resposta_esperada: str, resposta_gerada: str, fontes: list[str]
) -> dict:
    fontes_texto = "\n".join(f"- {f}" for f in fontes) if fontes else "(nenhuma fonte recuperada)"
    prompt = _JUDGE_PROMPT_TEMPLATE.format(
        pergunta=pergunta,
        resposta_esperada=resposta_esperada,
        fontes=fontes_texto,
        resposta_gerada=resposta_gerada,
    )
    # Achado ao rodar esta avaliação: 18 perguntas em sequência batem em
    # rate limit (429) do OpenRouter de vez em quando — retry com backoff
    # exponencial em vez de derrubar a rodada inteira por causa de um limite
    # transitório.
    for tentativa in range(_MAX_TENTATIVAS_JUIZ):
        try:
            resposta = await judge_client.generate(prompt)
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or tentativa == _MAX_TENTATIVAS_JUIZ - 1:
                raise
            espera_s = 2**tentativa
            numero = f"{tentativa + 1}/{_MAX_TENTATIVAS_JUIZ}"
            print(f"    429 do juiz ({numero}), aguardando {espera_s}s...")
            await asyncio.sleep(espera_s)
    try:
        return json.loads(strip_code_fence(resposta.text))
    except (json.JSONDecodeError, ValueError):  # fmt: skip
        return {"nota": None, "erro_parsing": resposta.text[:300]}


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
    rag_client = ActiveCollectionRagClient(qdrant, session_factory, embedders)

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

    resultados = []
    for caso in casos:
        print(f"[{caso['id']}] {caso['pergunta'][:70]}...")
        documentos = await _buscar_documentos_rag(
            caso["pergunta"], recent_messages=[], domain=_DOMAIN, rag_client=rag_client
        )
        prompt = _build_prompt(caso["pergunta"], documentos, domain=_DOMAIN)
        resposta_llm = await local_client.generate(prompt)
        resposta_gerada = resposta_llm.text
        fontes = [documento.source for documento in documentos]
        fonte_correta = _fonte_e_correta(fontes, caso["documento_origem"])

        julgamento = await _julgar_resposta(
            judge_client, caso["pergunta"], caso["resposta_esperada"], resposta_gerada, fontes
        )

        resultados.append(
            {
                "id": caso["id"],
                "pergunta": caso["pergunta"],
                "dificuldade": caso["dificuldade"],
                "documento_origem_esperado": caso["documento_origem"],
                "resposta_esperada": caso["resposta_esperada"],
                "resposta_gerada": resposta_gerada,
                "fontes_recuperadas": fontes,
                "fonte_correta": fonte_correta,
                "nota_llm_judge": julgamento,
                "nota_manual": None,
            }
        )
        print(f"    fonte_correta={fonte_correta}  nota_llm_judge={julgamento.get('nota')}")

    output_path = BASE_DIR / "results.json"
    output_path.write_text(
        json.dumps({"casos": resultados}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nResultados salvos em {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
