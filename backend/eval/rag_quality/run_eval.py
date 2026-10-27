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
    .venv/bin/python eval/rag_quality/run_eval.py --sem-resposta   # só as 20 negativas
    .venv/bin/python eval/rag_quality/run_eval.py --sem-resposta --sem-juiz  # sem chamar o juiz
    .venv/bin/python eval/rag_quality/run_eval.py --com-resposta [--prompt-v2]  # 143 respondíveis
    .venv/bin/python eval/rag_quality/run_eval.py --com-resposta --top-k 5 --saida results_x.json

Salva `eval/rag_quality/results.json`.
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.qdrant_client import QdrantRAGClient
from app.router.classifier import normalize, strip_code_fence
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.orchestrator import _build_prompt, _buscar_documentos_rag

BASE_DIR = Path(__file__).parent
_DOMAIN = "suporte"
# Contexto padrão da avaliação. A produção usa `local_llm_num_ctx = null`
# (padrão do Ollama); aqui 8192 evita o timeout/truncamento do caso 80 da
# Etapa 4 (prompt de ~3,5 mil tokens). `LOCAL_LLM_NUM_CTX` no ambiente prevalece.
_NUM_CTX_PADRAO_AVALIACAO = 8192

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


# Prompt novo (2026-10-17) para os casos `sem_resposta`: ali o gabarito não é
# um fato, é a recusa. Pedir nota 1-5 de "correção factual" contra um gabarito
# que diz "não consta" confundiria o juiz — a pergunta certa é binária: ele
# admitiu não ter a informação ou inventou?
_JUDGE_PROMPT_SEM_RESPOSTA = """\
Você é um avaliador técnico imparcial. A pergunta abaixo **não tem resposta** \
no acervo de documentos do assistente: o comportamento correto é admitir que \
não tem a informação, sem inventar dado, número ou fonte.

Pergunta: {pergunta}

Fontes que o assistente recuperou (podem ser irrelevantes ou vazias):
{fontes}

Resposta gerada pelo assistente: {resposta_gerada}

Avalie:
- "recusou": true se a resposta admite claramente não ter a informação \
(ou pede mais contexto/encaminha a um humano) em vez de responder.
- "alucinou": true se a resposta afirma qualquer dado técnico específico \
(número, especificação, modelo, procedimento) como se constasse do acervo.
- Atenção: "recusou" e "alucinou" podem ser os dois true, quando a resposta \
mistura ressalva com dado inventado. Isso conta como alucinação.

Responda APENAS com JSON: {{"recusou": true/false, "alucinou": true/false, \
"justificativa": "<1-2 frases>"}}."""

# Marcadores de recusa, só como segundo sinal ao lado do juiz: se o juiz
# falhar (JSON inválido, rate limit), ainda sobra uma medida determinística
# em vez de um buraco no resultado.
_MARCADORES_RECUSA = (
    "nao tenho",
    "nao consta",
    "nao encontrei",
    "nao localizei",
    "nao foi possivel encontrar",
    "nao disponho",
    "sem informacao",
    "nao ha informacao",
    "nao posso afirmar",
    "nao sei",
)


def _parece_recusa(texto: str) -> bool:
    normalizado = re.sub(r"\s+", " ", normalize(texto or ""))
    return any(marcador in normalizado for marcador in _MARCADORES_RECUSA)


def _carregar_casos() -> list[dict]:
    dados = json.loads((BASE_DIR / "dataset.json").read_text(encoding="utf-8"))
    return dados["casos"]


# Variante de prompt em teste (`--prompt-v2`, experimento da Etapa 4): troca a
# instrução que manda "responder com o que souber" por uma que manda admitir
# que não achou, e avisa explicitamente quando a busca volta vazia. Fica só aqui,
# no eval: o prompt de produção (`orchestrator._build_prompt`) não muda até a
# decisão de arquitetura.
_FRASE_V1 = (
    "Se as informações não forem suficientes, responda com o que souber, sem "
    "inventar dados específicos (preços, prazos, números de série)."
)
_FRASE_V2 = (
    "Se as informações não responderem à pergunta, diga claramente que não "
    "encontrou essa informação na base de conhecimento e oriente o cliente a "
    "falar com um atendente ou consultar o manual do produto; não responda com "
    "conhecimento próprio nem invente dados específicos (preços, prazos, "
    "números de série, procedimentos)."
)
_AVISO_SEM_CONTEXTO_V2 = (
    "\n\nNenhuma informação foi encontrada na base de conhecimento da empresa "
    "para esta pergunta. Diga claramente que não encontrou essa informação e "
    "oriente o cliente a falar com um atendente; não responda com conhecimento "
    "próprio nem invente dados."
)


def _nome_saida(so_negativas: bool, so_respondiveis: bool, prompt_v2: bool) -> str:
    if not (so_negativas or so_respondiveis or prompt_v2):
        return "results.json"
    modo = "sem_resposta" if so_negativas else "respondiveis" if so_respondiveis else "completo"
    return f"results_{modo}_{'v2' if prompt_v2 else 'v1'}.json"


def _aplicar_prompt_v2(prompt: str, tem_documentos: bool) -> str:
    if not tem_documentos:
        return prompt + _AVISO_SEM_CONTEXTO_V2
    if _FRASE_V1 not in prompt:
        # Falha alto: senão a rodada "v2" mediria o prompt v1 sem avisar.
        raise RuntimeError("frase de suficiência do prompt mudou; atualize _FRASE_V1")
    return prompt.replace(_FRASE_V1, _FRASE_V2)


def _so_respondiveis_revisados(casos: list[dict]) -> list[dict]:
    """Os casos com resposta aprovados/corrigidos, sem duplicata nem origem ambígua."""
    return [
        c
        for c in casos
        if not c.get("sem_resposta")
        and (c.get("revisao") or {}).get("status") in {"aprovado", "corrigido"}
        and not c.get("duplicada_de")
        and not c.get("origem_ambigua")
    ]


def _so_sem_resposta_revisados(casos: list[dict]) -> list[dict]:
    """Os casos `sem_resposta` aprovados ou corrigidos na revisão, sem duplicatas."""
    return [
        c
        for c in casos
        if c.get("sem_resposta")
        and (c.get("revisao") or {}).get("status") in {"aprovado", "corrigido"}
        and not c.get("duplicada_de")
    ]


def _normalizar_nome_arquivo(nome: str) -> str:
    # Achado ao rodar esta avaliação: um dos PDFs enviados por upload tem
    # espaço duplo no nome real do arquivo ("...IA  FT..."), diferente do
    # nome usado no gabarito (`dataset.json`) — comparação ingênua marcava
    # falso negativo em "fonte_correta" mesmo quando o documento certo foi
    # de fato recuperado. Colapsa espaços antes de comparar.
    return re.sub(r"\s+", " ", nome.lower()).strip()


async def _julgar_recusa(
    judge_client, pergunta: str, resposta_gerada: str, fontes: list[str]
) -> dict:
    """Julga um caso `sem_resposta`: recusou ou alucinou?"""
    fontes_texto = "\n".join(f"- {f}" for f in fontes) if fontes else "(nenhuma fonte recuperada)"
    prompt = _JUDGE_PROMPT_SEM_RESPOSTA.format(
        pergunta=pergunta, fontes=fontes_texto, resposta_gerada=resposta_gerada
    )
    resposta = await _gerar_com_retry(judge_client, prompt)
    await asyncio.sleep(PAUSA_ENTRE_CHAMADAS_S)
    try:
        return json.loads(strip_code_fence(resposta.text))
    except (ValueError, TypeError) as exc:
        return {"erro": f"JSON inválido do juiz: {exc}"}


def _fonte_e_correta(
    fontes: list[str], documento_origem: str, documentos_aceitos: list[str] | None = None
) -> bool:
    """`documentos_aceitos`: PDFs gêmeos (v1/v2, guia/datasheet) com a mesma evidência."""
    origens = [_normalizar_nome_arquivo(d) for d in [documento_origem, *(documentos_aceitos or [])]]
    return any(o in _normalizar_nome_arquivo(f) for o in origens for f in fontes)


_MAX_TENTATIVAS_JUIZ = 6
# `EXTERNAL_MODEL_NAME` aponta pro tier `:free` do OpenRouter (ver .env),
# com limite de requisições por minuto bem mais apertado que um modelo
# pago — um backoff curto (1,2,4s) não dava tempo de o limite liberar de
# novo. Começa em 8s, dobra a cada tentativa (8,16,32,64,128s).
_ESPERA_BASE_S = 8.0
# Pausa proativa entre chamadas do juiz, não só reativa a 429 — reduz
# quantas vezes o limite é batido, importante em `chunk_size_search.py`
# (várias rodadas de 18 perguntas em sequência).
PAUSA_ENTRE_CHAMADAS_S = 3.0


async def _gerar_com_retry(judge_client, prompt: str):
    """Chama o juiz repetindo em 429 e em timeout (`httpx.TimeoutException`).

    Antes só o 429 era repetido; um `ReadTimeout` do juiz subia sem retry e
    derrubava a rodada inteira no meio.
    """
    for tentativa in range(_MAX_TENTATIVAS_JUIZ):
        try:
            return await judge_client.generate(prompt)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            limitado = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
            if not (limitado or isinstance(exc, httpx.TimeoutException)):
                raise
            if tentativa == _MAX_TENTATIVAS_JUIZ - 1:
                raise
            espera_s = _ESPERA_BASE_S * (2**tentativa)
            numero = f"{tentativa + 1}/{_MAX_TENTATIVAS_JUIZ}"
            motivo = "429" if limitado else "timeout"
            print(f"    {motivo} do juiz ({numero}), aguardando {espera_s:.0f}s...")
            await asyncio.sleep(espera_s)
    raise AssertionError("inalcançável")  # pragma: no cover


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
    # Achado ao rodar esta avaliação: perguntas em sequência batem em rate
    # limit (429) do OpenRouter com frequência (modelo `:free`, ver
    # `_ESPERA_BASE_S` acima) — retry com backoff exponencial mais paciente
    # em vez de derrubar a rodada inteira por causa de um limite transitório.
    resposta = await _gerar_com_retry(judge_client, prompt)
    await asyncio.sleep(PAUSA_ENTRE_CHAMADAS_S)
    try:
        return json.loads(strip_code_fence(resposta.text))
    except (json.JSONDecodeError, ValueError):  # fmt: skip
        return {"nota": None, "erro_parsing": resposta.text[:300]}


def _resumo(resultados: list[dict], sem_resposta: list[dict]) -> dict:
    # `casos` fica só com os respondíveis para não quebrar o agregado público
    # (`app.api.avaliacao._rag` usa `len(casos)` como denominador de
    # `fonte_correta`): com os 20 sem resposta na mesma lista, a taxa de fonte
    # cairia por construção.
    return {
        "respondiveis": len(resultados),
        "sem_resposta": len(sem_resposta),
        "recusou": sum(1 for c in sem_resposta if c["recusou"]),
        "alucinou": sum(1 for c in sem_resposta if c["alucinou"]),
        "recusa_por_marcador": sum(1 for c in sem_resposta if c["recusa_por_marcador"]),
    }


# Configuração da rodada, preenchida em `main()` e gravada junto dos resultados:
# sem ela, duas rodadas com `num_ctx` ou juiz diferentes (como a retomada da
# Etapa 5, que misturou 4096 e 8192) ficam indistinguíveis no JSON.
_CONFIGURACAO: dict = {}
# Fração do contexto efetivo a partir da qual o prompt é considerado em risco
# de truncamento silencioso pelo Ollama.
_LIMITE_OCUPACAO_CONTEXTO = 0.8
_MAX_TENTATIVAS_LOCAL = 3
_ESPERA_LOCAL_S = 15.0


async def _gerar_local_com_retry(local_client, prompt: str):
    """Gera no modelo local repetindo em timeout e em 5xx do Ollama.

    Um crash do llama-server (ex.: `CUDA error` no caso 160 da Etapa 5)
    devolve 500 e o Ollama o recarrega sozinho; a espera dá tempo disso.
    """
    for tentativa in range(_MAX_TENTATIVAS_LOCAL):
        try:
            return await local_client.generate(prompt)
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            servidor = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500
            if not (servidor or isinstance(exc, httpx.TimeoutException)):
                raise
            if tentativa == _MAX_TENTATIVAS_LOCAL - 1:
                raise
            numero = f"{tentativa + 1}/{_MAX_TENTATIVAS_LOCAL}"
            print(f"    falha do modelo local ({type(exc).__name__}, {numero}), reaguardando...")
            await asyncio.sleep(_ESPERA_LOCAL_S)
    raise AssertionError("inalcançável")  # pragma: no cover


async def _contexto_efetivo(local_client) -> int | None:
    """`context_length` que o Ollama realmente carregou (`/api/ps`)."""
    status = await local_client.get_loaded_status()
    return (status or {}).get("context_length")


def _avisar_ocupacao(prompt_tokens: int | None, contexto: int | None) -> bool:
    """Avisa se o prompt ocupa demais do contexto; devolve se está em risco."""
    if not prompt_tokens or not contexto:
        return False
    em_risco = prompt_tokens > _LIMITE_OCUPACAO_CONTEXTO * contexto
    if em_risco:
        print(f"    AVISO: prompt de {prompt_tokens} tokens em contexto de {contexto}")
    return em_risco


def _gravar_resultados(path: Path, resultados: list[dict], sem_resposta: list[dict]) -> None:
    """Grava o estado atual; chamada a cada caso para uma falha não perder a rodada."""
    path.write_text(
        json.dumps(
            {
                "configuracao": _CONFIGURACAO,
                "casos": resultados,
                "casos_sem_resposta": sem_resposta,
                "resumo": _resumo(resultados, sem_resposta),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _opcao(nome: str, padrao: str | None = None) -> str | None:
    """Valor de `--nome valor` em `sys.argv` (ou `padrao`)."""
    if nome in sys.argv:
        return sys.argv[sys.argv.index(nome) + 1]
    return padrao


async def main() -> None:
    settings = get_settings()
    casos = _carregar_casos()
    # Modo `--sem-resposta`: só as negativas revisadas, saída em arquivo próprio
    # (não sobrescreve o `results.json` da rodada completa).
    so_negativas = "--sem-resposta" in sys.argv
    so_respondiveis = "--com-resposta" in sys.argv
    prompt_v2 = "--prompt-v2" in sys.argv
    if so_negativas:
        casos = _so_sem_resposta_revisados(casos)
    elif so_respondiveis:
        casos = _so_respondiveis_revisados(casos)
    output_path = BASE_DIR / (
        _opcao("--saida") or _nome_saida(so_negativas, so_respondiveis, prompt_v2)
    )
    top_k = int(_opcao("--top-k", "3"))

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

    num_ctx = settings.local_llm_num_ctx or _NUM_CTX_PADRAO_AVALIACAO
    local_client = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=settings.local_llm_timeout_s,
        temperature=settings.local_llm_temperature,
        num_ctx=num_ctx,
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
    resultados_sem_resposta: list[dict] = []
    # `--retomar`: continua uma rodada interrompida, reaproveitando os casos já
    # gravados em `output_path` e pulando os seus ids.
    if "--retomar" in sys.argv and output_path.exists():
        anterior = json.loads(output_path.read_text(encoding="utf-8"))
        resultados = anterior.get("casos", [])
        resultados_sem_resposta = anterior.get("casos_sem_resposta", [])
    _CONFIGURACAO.update(
        modelo_local=settings.local_model_name,
        modelo_juiz=settings.external_model_name,
        num_ctx_configurado=num_ctx,
        local_llm_timeout_s=settings.local_llm_timeout_s,
        prompt_v2=prompt_v2,
        top_k=top_k,
    )
    if "--retomar" in sys.argv and output_path.exists():
        anterior_cfg = json.loads(output_path.read_text(encoding="utf-8")).get("configuracao")
        if anterior_cfg != _CONFIGURACAO:
            print(f"AVISO: retomada com configuração diferente: {anterior_cfg} -> {_CONFIGURACAO}")
    ja_feitos = {str(c["id"]) for c in resultados + resultados_sem_resposta}
    for caso in casos:
        if str(caso["id"]) in ja_feitos:
            continue
        _gravar_resultados(output_path, resultados, resultados_sem_resposta)
        print(f"[{caso['id']}] {caso['pergunta'][:70]}...")
        documentos = await _buscar_documentos_rag(
            caso["pergunta"], recent_messages=[], domain=_DOMAIN, rag_client=rag_client, top_k=top_k
        )
        prompt = _build_prompt(caso["pergunta"], documentos, domain=_DOMAIN)
        if prompt_v2:
            prompt = _aplicar_prompt_v2(prompt, bool(documentos))
        resposta_llm = await _gerar_local_com_retry(local_client, prompt)
        resposta_gerada = resposta_llm.text
        contexto = await _contexto_efetivo(local_client)
        _CONFIGURACAO["num_ctx_efetivo"] = contexto
        prompt_tokens = resposta_llm.prompt_tokens
        contexto_em_risco = _avisar_ocupacao(prompt_tokens, contexto)
        fontes = [documento.source for documento in documentos]

        # Os casos `sem_resposta` medem alucinação, não recuperação: o
        # gabarito é a recusa, `documento_origem` é vazio de propósito e não
        # existe fonte correta a cobrar. Antes de 2026-10-17 eles passavam
        # pelo mesmo caminho dos respondíveis — `_fonte_e_correta` devolvia
        # False por construção e o juiz comparava a resposta com um gabarito
        # que não é um fato. Agora são julgados por outro prompt e somados
        # num resultado separado, porque misturar os dois no mesmo
        # denominador estraga as duas medidas.
        if caso.get("sem_resposta"):
            # `--sem-juiz`: o tier gratuito esgota o limite diário (429) no meio da
            # rodada; sem juiz, a recusa fica com o marcador e a leitura humana.
            if "--sem-juiz" in sys.argv:
                julgamento = {}
            else:
                julgamento = await _julgar_recusa(
                    judge_client, caso["pergunta"], resposta_gerada, fontes
                )
            recusa_heuristica = _parece_recusa(resposta_gerada)
            resultados_sem_resposta.append(
                {
                    "id": caso["id"],
                    "pergunta": caso["pergunta"],
                    "resposta_gerada": resposta_gerada,
                    "fontes_recuperadas": fontes,
                    "recusou": julgamento.get("recusou"),
                    "alucinou": julgamento.get("alucinou"),
                    "recusa_por_marcador": recusa_heuristica,
                    "julgamento": julgamento,
                    "prompt_tokens": prompt_tokens,
                    "contexto_em_risco": contexto_em_risco,
                    "nota_manual": None,
                }
            )
            print(
                f"    [sem resposta] recusou={julgamento.get('recusou')} "
                f"alucinou={julgamento.get('alucinou')} marcador={recusa_heuristica}"
            )
            continue

        fonte_correta = _fonte_e_correta(
            fontes, caso["documento_origem"], caso.get("documentos_aceitos")
        )

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
                "prompt_tokens": prompt_tokens,
                "contexto_em_risco": contexto_em_risco,
                "nota_manual": None,
            }
        )
        print(f"    fonte_correta={fonte_correta}  nota_llm_judge={julgamento.get('nota')}")

    _gravar_resultados(output_path, resultados, resultados_sem_resposta)
    print(f"\nResultados salvos em {output_path}")
    print(f"Resumo: {_resumo(resultados, resultados_sem_resposta)}")


if __name__ == "__main__":
    asyncio.run(main())
