"""Orquestrador do benchmark comparativo entre os modelos locais candidatos
(Fase 10, item 1 do roadmap) — ver docs/EVALUATION.md e docs/ARCHITECTURE.md,
tabela de escopo, linha "Modelo local".

Mede cada candidato **contra o sistema completo**, não isoladamente: as
mesmas três avaliações já existentes em `eval/` (acerto do roteador,
qualidade do RAG e resistência a prompt injection) são reexecutadas trocando
só o modelo local, reaproveitando os datasets e o caminho real de produção
(`classify`, `_buscar_documentos_rag`, `_build_prompt`). Foi deliberadamente
deixado para o fim do roadmap: medir antes de RAG e playbooks existirem
descartaria/escolheria um modelo com sinal incompleto.

Uso (a partir de `backend/`, com Ollama no ar; as etapas `rag` e `injecao`
também exigem `EXTERNAL_MODEL_API_KEY` no `.env` para o LLM-as-judge, e a
`rag` exige Qdrant/Postgres com o corpus já ingerido):

    .venv/bin/python eval/model_benchmark/run_benchmark.py --listar
    .venv/bin/python eval/model_benchmark/run_benchmark.py --etapas roteador
    .venv/bin/python eval/model_benchmark/run_benchmark.py --modelos gemma4-12b-q4

Salva um arquivo por modelo em `eval/model_benchmark/results/<id>.json`, no
envelope que `GET /api/avaliacao/resultados` já lê
(`app.api.avaliacao._modelos`): `{versao, avaliacao, modelo, gerado_em,
config, metricas, itens}`. Só `modelo`, `gerado_em`, `config` e `metricas`
saem pela API pública — `itens` guarda as respostas geradas e fica fora.

**Retomável:** cada etapa é gravada assim que termina. Rodar de novo pula as
etapas que já estão no arquivo do modelo (use `--forcar` para refazer). Uma
rodada completa leva horas e o processo pode cair (OOM de VRAM, queda do
Ollama, rate limit do juiz) — perder tudo a cada queda inviabilizaria a
medição.
"""

import argparse
import asyncio
import json
import sys
import time
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.config import get_settings
from app.db.engine import create_db_engine, create_session_factory
from app.rag.active_collection_client import ActiveCollectionRagClient
from app.rag.embedders_registry import EmbedderRegistry
from app.rag.image_identification import _VISION_PROMPT, _parse_vision_answer
from app.rag.qdrant_client import QdrantRAGClient
from app.router.classifier import Domain, _parse_llm_classification, classify
from app.router.llm_client import VisionModelIndisponivelError
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient
from app.router.orchestrator import _build_prompt, _buscar_documentos_rag

BASE_DIR = Path(__file__).parent
RESULTS_DIR = BASE_DIR / "results"
EVAL_DIR = BASE_DIR.parent

# Os critérios de julgamento das etapas `rag` e `injecao` são os mesmos dos
# evals originais — importados de lá para não existirem duas versões do
# mesmo prompt de juiz. Mesmo padrão de `rag_quality/chunk_size_search.py`,
# mas pela pasta `eval/` (os dois módulos se chamam `run_eval`, então
# importar pelo nome curto colidiria em `sys.modules`).
sys.path.insert(0, str(EVAL_DIR))
from prompt_injection.run_eval import _avaliar_cliente  # noqa: E402
from rag_quality.run_eval import _fonte_e_correta, _julgar_resposta  # noqa: E402

VERSAO_ENVELOPE = 1
ETAPAS = ("roteador", "rag", "injecao", "imagem")
# Raiz do repositório — os caminhos de imagem do dataset são relativos a ela.
REPO_DIR = EVAL_DIR.parent.parent
_DOMINIOS: list[Domain] = ["vendas", "suporte", "atendimento", "agendamento"]

# MVP: a primeira chamada depois de trocar de modelo paga a carga na VRAM
# (medido: ~13s com carga vs. resposta quase imediata com o modelo quente).
# O timeout precisa ser bem maior que o LOCAL_LLM_TIMEOUT_S de produção (30s),
# senão candidatos grandes (14B Q5/Q8 em 16GB) falham por tempo de carga, não
# por qualidade — o que não é o que este benchmark quer medir.
TIMEOUT_PADRAO_S = 180.0


# --------------------------------------------------------------------------
# Instrumentação
# --------------------------------------------------------------------------


class ClienteInstrumentado:
    """Embrulha o cliente local para medir cada `generate` sem tocar no
    caminho de produção.

    Registra a latência ponta a ponta de toda chamada e, quando
    `checar_json_classificacao` está ligado, se o texto devolvido era um JSON
    de classificação válido. Esse segundo número não dá para tirar do
    resultado de `classify()`: quando o modelo devolve JSON quebrado, o
    classificador cai para a heurística **mantendo**
    `provider_efetivo="heuristica_llm"` (`_classify_with_llm`), então de fora
    a falha é indistinguível de um acerto. Em um benchmark de modelos isso
    importa: um candidato pode ter acurácia parecida e ser muito pior em
    seguir o formato pedido.
    """

    def __init__(self, inner: OllamaClient) -> None:
        self._inner = inner
        self.latencias_s: list[float] = []
        self.json_validos = 0
        self.json_invalidos = 0
        self.checar_json_classificacao = False

    def zerar(self) -> None:
        self.latencias_s = []
        self.json_validos = 0
        self.json_invalidos = 0

    async def generate(self, prompt: str):
        inicio = time.perf_counter()
        resposta = await self._inner.generate(prompt)
        self.latencias_s.append(time.perf_counter() - inicio)
        if self.checar_json_classificacao:
            try:
                _parse_llm_classification(resposta.text)
                self.json_validos += 1
            except (json.JSONDecodeError, ValidationError, TypeError):  # fmt: skip
                self.json_invalidos += 1
        return resposta


def percentil_95(valores: list[float]) -> float | None:
    """p95 por interpolação linear entre os pontos mais próximos.

    Com as amostras pequenas deste benchmark (18 a 40 chamadas por etapa),
    pegar "o elemento no índice 0.95*n" joga o p95 em cima do máximo e perde
    a diferença entre candidatos; a interpolação mantém o número estável.
    """
    if not valores:
        return None
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return round(ordenados[0], 3)
    k = 0.95 * (len(ordenados) - 1)
    inferior = int(k)
    superior = min(inferior + 1, len(ordenados) - 1)
    peso = k - inferior
    return round(ordenados[inferior] * (1 - peso) + ordenados[superior] * peso, 3)


# --------------------------------------------------------------------------
# Envelope de resultado (retomada)
# --------------------------------------------------------------------------


def caminho_do_resultado(candidato: dict) -> Path:
    return RESULTS_DIR / f"{candidato['id']}.json"


def carregar_envelope(candidato: dict) -> dict:
    caminho = caminho_do_resultado(candidato)
    if caminho.exists():
        envelope = json.loads(caminho.read_text(encoding="utf-8"))
        envelope.setdefault("itens", {})
        envelope.setdefault("metricas", {})
        return envelope
    return {
        "versao": VERSAO_ENVELOPE,
        "avaliacao": "model_benchmark",
        "modelo": candidato["rotulo"],
        "gerado_em": None,
        "config": {},
        "metricas": {},
        "itens": {},
    }


def etapas_pendentes(envelope: dict, pedidas: list[str], forcar: bool) -> list[str]:
    if forcar:
        return list(pedidas)
    return [etapa for etapa in pedidas if etapa not in envelope["itens"]]


def consolidar_metricas(envelope: dict) -> None:
    """Recalcula `metricas` a partir de todas as etapas já gravadas.

    Chamado depois de cada etapa: a latência é agregada sobre o conjunto de
    etapas presentes no arquivo, então uma rodada retomada produz o mesmo
    número que uma rodada única — não a média só da última etapa.
    """
    itens = envelope["itens"]
    metricas: dict = dict(envelope.get("metricas", {}))

    if "roteador" in itens:
        roteador = itens["roteador"]
        metricas["roteador_acuracia"] = roteador["acuracia"]
        metricas["roteador_acertos"] = roteador["acertos"]
        metricas["roteador_total"] = roteador["total"]
        metricas["json_invalido_taxa"] = roteador["json_invalido_taxa"]
    if "rag" in itens:
        rag = itens["rag"]
        metricas["rag_nota_media"] = rag["nota_media"]
        metricas["rag_fonte_correta_taxa"] = rag["fonte_correta_taxa"]
        metricas["rag_total"] = rag["total"]
    if "injecao" in itens:
        injecao = itens["injecao"]
        metricas["injecao_resistencia"] = injecao["taxa_resistencia"]
        metricas["injecao_comprometidos"] = injecao["comprometidos"]
        metricas["injecao_total"] = injecao["total"]
    if "imagem" in itens:
        imagem = itens["imagem"]
        # `false` é resultado, não ausência de medição: diz que a imagem do
        # cliente cairia para a visão externa com este candidato.
        metricas["visao_local"] = imagem["suportado_localmente"]
        if imagem["suportado_localmente"]:
            metricas["imagem_portfolio_acerto"] = imagem["portfolio_acerto_taxa"]
            metricas["imagem_categoria_acerto"] = imagem["categoria_acerto_taxa"]
            metricas["imagem_json_valido_taxa"] = imagem["json_valido_taxa"]
            metricas["imagem_total"] = imagem["total"]

    latencias = [s for etapa in itens.values() for s in etapa.get("latencias_s", [])]
    if latencias:
        metricas["latencia_media_s"] = round(sum(latencias) / len(latencias), 3)
        metricas["latencia_p95_s"] = percentil_95(latencias)
        metricas["chamadas_medidas"] = len(latencias)

    envelope["metricas"] = metricas


def gravar_envelope(candidato: dict, envelope: dict) -> Path:
    envelope["gerado_em"] = datetime.now(UTC).isoformat(timespec="seconds")
    caminho = caminho_do_resultado(candidato)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8")
    return caminho


# --------------------------------------------------------------------------
# Etapas
# --------------------------------------------------------------------------


def _carregar_dataset(subpasta: str) -> list[dict]:
    dados = json.loads((EVAL_DIR / subpasta / "dataset.json").read_text(encoding="utf-8"))
    return dados["casos"]


async def etapa_roteador(cliente: ClienteInstrumentado, external_client) -> dict:
    """Acurácia do roteador (eval/router_intents) com este modelo no papel de
    LLM local do provider `heuristica_llm` — o caminho de produção."""
    casos = _carregar_dataset("router_intents")
    cliente.zerar()
    cliente.checar_json_classificacao = True

    matriz: dict[str, dict[str, int]] = {esperado: {} for esperado in _DOMINIOS}
    erros: list[dict] = []
    acertos = 0

    for caso in casos:
        resultado = await classify(
            caso["mensagem"],
            recent_messages=[],
            # `provider="heuristica_llm"` sem `strategy="llm"` nunca chega a
            # chamar o LLM (achado registrado em eval/router_intents).
            strategy="llm",
            llm_client=cliente,
            provider="heuristica_llm",
            external_client=external_client,
        )
        esperado = caso["intencao_esperada"]
        previsto = resultado.domain
        matriz[esperado][previsto] = matriz[esperado].get(previsto, 0) + 1
        if previsto == esperado:
            acertos += 1
        else:
            erros.append(
                {
                    "id": caso["id"],
                    "esperado": esperado,
                    "previsto": previsto,
                    "ambiguo": caso.get("ambiguo", False),
                }
            )

    cliente.checar_json_classificacao = False
    total = len(casos)
    tentativas_json = cliente.json_validos + cliente.json_invalidos
    return {
        "acuracia": round(acertos / total, 4) if total else None,
        "acertos": acertos,
        "total": total,
        "json_invalidos": cliente.json_invalidos,
        "json_tentativas": tentativas_json,
        "json_invalido_taxa": (
            round(cliente.json_invalidos / tentativas_json, 4) if tentativas_json else None
        ),
        "matriz_confusao": matriz,
        "erros": erros,
        "latencias_s": [round(s, 3) for s in cliente.latencias_s],
    }


async def etapa_rag(cliente: ClienteInstrumentado, rag_client, judge_client) -> dict:
    """Qualidade do RAG (eval/rag_quality) gerando com este modelo e julgando
    com o LLM externo — mesmo juiz e mesmo prompt do eval original, importado
    dali para não haver duas versões do critério."""
    casos = _carregar_dataset("rag_quality")
    cliente.zerar()

    resultados: list[dict] = []
    notas: list[float] = []
    fontes_corretas = 0

    for caso in casos:
        documentos = await _buscar_documentos_rag(
            caso["pergunta"], recent_messages=[], domain="suporte", rag_client=rag_client
        )
        prompt = _build_prompt(caso["pergunta"], documentos, domain="suporte")
        resposta = await cliente.generate(prompt)
        fontes = [documento.source for documento in documentos]
        fonte_correta = _fonte_e_correta(fontes, caso["documento_origem"])
        fontes_corretas += int(fonte_correta)

        julgamento = await _julgar_resposta(
            judge_client,
            caso["pergunta"],
            caso["resposta_esperada"],
            resposta.text,
            fontes,
        )
        nota = julgamento.get("nota")
        if isinstance(nota, (int, float)):  # fmt: skip
            notas.append(float(nota))

        resultados.append(
            {
                "id": caso["id"],
                "fontes_recuperadas": fontes,
                "fonte_correta": fonte_correta,
                "resposta_gerada": resposta.text,
                "nota_llm_judge": julgamento,
            }
        )
        print(f"    [{caso['id']}] fonte_correta={fonte_correta} nota={nota}")

    total = len(casos)
    return {
        "nota_media": round(sum(notas) / len(notas), 3) if notas else None,
        "notas_validas": len(notas),
        "fonte_correta_taxa": round(fontes_corretas / total, 4) if total else None,
        "total": total,
        "casos": resultados,
        "latencias_s": [round(s, 3) for s in cliente.latencias_s],
    }


async def etapa_injecao(cliente: ClienteInstrumentado, judge_client) -> dict:
    """Resistência a prompt injection (eval/prompt_injection) com este modelo
    no papel de cliente local."""
    cliente.zerar()
    casos = _carregar_dataset("prompt_injection")
    bruto = await _avaliar_cliente("local", cliente, casos, judge_client)
    return {
        "taxa_resistencia": bruto["taxa_resistencia"],
        "comprometidos": bruto["comprometidos"],
        "total": bruto["total_casos"],
        "casos": bruto["casos"],
        "latencias_s": [round(s, 3) for s in cliente.latencias_s],
    }


def _sem_acento(texto: str) -> str:
    """Minúsculas e sem acento, para o casamento de categoria.

    Sem isso, `"biometri"` não casa com `"biométrico"` (o modelo escreve em
    português acentuado e o termo aceito, não) e o acerto vira erro — o que
    de fato aconteceu na primeira execução desta etapa, em 2026-10-16.
    """
    decomposto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _acertou_categoria(produto_previsto: str, aceitos: list[str]) -> bool:
    previsto = _sem_acento(produto_previsto)
    return any(_sem_acento(termo) in previsto for termo in aceitos)


async def etapa_imagem(inner: OllamaClient, tem_visao: bool) -> dict:
    """Identificação de produto por imagem (R2/R5) com a visão LOCAL deste
    modelo — mesmo `_VISION_PROMPT` e mesmo parse de `app.rag.image_identification`.

    Modelo sem capability `vision` não é pulado em silêncio: o resultado
    registra `suportado_localmente: false`. Não é lacuna de medição, é o
    resultado — significa que toda imagem do cliente cairia para a visão
    EXTERNA (custo por token e a imagem saindo da máquina), que é justamente
    o trade-off que esta comparação existe para expor.

    Pontuação determinística, sem LLM-as-judge: o gabarito é objetivo. Não se
    exige o SKU exato, porque no fluxo real quem identifica com precisão é o
    CLIP contra o catálogo interno — a visão é o fallback que só precisa
    dizer se é do portfólio e, grosso modo, o que é.
    """
    if not tem_visao:
        return {
            "suportado_localmente": False,
            "observacao": (
                "Modelo sem capability 'vision' no Ollama: no sistema real "
                "`describe_image` levanta VisionModelIndisponivelError e a imagem "
                "cai para a visão externa."
            ),
            "latencias_s": [],
        }

    dados = json.loads((BASE_DIR / "imagens" / "dataset.json").read_text(encoding="utf-8"))
    casos = dados["casos"]

    resultados: list[dict] = []
    latencias: list[float] = []
    json_validos = 0
    portfolio_ok = 0
    categoria_ok = 0

    for caso in casos:
        caminho = REPO_DIR / caso["caminho"]
        imagem = caminho.read_bytes()
        inicio = time.perf_counter()
        try:
            bruto = await inner.describe_image(imagem, _VISION_PROMPT)
            texto = bruto.content
        except VisionModelIndisponivelError as exc:
            texto = ""
            print(f"    [{caso['id']}] visão indisponível: {exc}")
        latencias.append(time.perf_counter() - inicio)

        resposta = _parse_vision_answer(texto) if texto else None
        if resposta is None:
            resultados.append({"id": caso["id"], "json_valido": False, "bruto": texto[:300]})
            print(f"    [{caso['id']}] JSON inválido")
            continue

        json_validos += 1
        acerto_portfolio = resposta.e_do_portfolio == caso["e_do_portfolio"]
        acerto_categoria = _acertou_categoria(resposta.produto, caso["aceitos"])
        portfolio_ok += int(acerto_portfolio)
        categoria_ok += int(acerto_categoria)
        resultados.append(
            {
                "id": caso["id"],
                "json_valido": True,
                "produto_esperado": caso["produto_esperado"],
                "produto_previsto": resposta.produto,
                "e_do_portfolio_previsto": resposta.e_do_portfolio,
                "confianca": resposta.confianca,
                "acerto_portfolio": acerto_portfolio,
                "acerto_categoria": acerto_categoria,
            }
        )
        print(
            f"    [{caso['id']}] '{resposta.produto}' "
            f"portfolio={acerto_portfolio} categoria={acerto_categoria}"
        )

    total = len(casos)
    return {
        "suportado_localmente": True,
        "total": total,
        "json_valido_taxa": round(json_validos / total, 4) if total else None,
        "portfolio_acerto_taxa": round(portfolio_ok / total, 4) if total else None,
        "categoria_acerto_taxa": round(categoria_ok / total, 4) if total else None,
        "casos": resultados,
        "latencias_s": [round(s, 3) for s in latencias],
    }


# --------------------------------------------------------------------------
# Orquestração
# --------------------------------------------------------------------------


async def modelos_baixados(base_url: str) -> set[str]:
    async with httpx.AsyncClient() as http:
        resposta = await http.get(f"{base_url.rstrip('/')}/api/tags", timeout=10.0)
        resposta.raise_for_status()
        return {m["name"] for m in resposta.json().get("models", [])}


def carregar_candidatos(ids: list[str] | None) -> list[dict]:
    dados = json.loads((BASE_DIR / "modelos.json").read_text(encoding="utf-8"))
    candidatos = dados["candidatos"]
    if not ids:
        return candidatos
    por_id = {c["id"]: c for c in candidatos}
    desconhecidos = [i for i in ids if i not in por_id]
    if desconhecidos:
        raise SystemExit(f"id(s) de modelo desconhecido(s): {', '.join(desconhecidos)}")
    return [por_id[i] for i in ids]


async def rodar_modelo(
    candidato: dict,
    etapas: list[str],
    forcar: bool,
    inner: OllamaClient,
    external_client,
    rag_client,
) -> None:
    envelope = carregar_envelope(candidato)
    pendentes = etapas_pendentes(envelope, etapas, forcar)
    if not pendentes:
        print(f"  etapas {', '.join(etapas)} já estão no arquivo — pulando (use --forcar)")
        return

    inner.model = candidato["ollama"]

    # Aquecimento descartado: a carga na VRAM é medida à parte (`carga_s`) e a
    # primeira geração não entra na latência, senão o custo de cold start
    # contamina a comparação entre candidatos.
    inicio_carga = time.perf_counter()
    await inner.preload()
    carga_s = round(time.perf_counter() - inicio_carga, 3)
    await inner.generate("Responda apenas: ok")
    status = await inner.get_loaded_status()
    vram_bytes = (status or {}).get("size_vram")

    # Capabilities vêm do próprio Ollama (`/api/show`), não de uma tabela
    # mantida à mão: é a mesma fonte que `describe_image` consulta para
    # decidir entre visão local e visão externa.
    detalhes = await inner.get_model_details(candidato["ollama"])
    capabilities = sorted((detalhes or {}).get("capabilities") or [])
    tem_visao = "vision" in capabilities
    print(
        f"  carga={carga_s}s  vram={_formatar_gb(vram_bytes)}  "
        f"visão_local={'sim' if tem_visao else 'não (cai para visão externa)'}"
    )

    envelope["config"] = {
        "ollama": candidato["ollama"],
        "familia": candidato["familia"],
        "parametros_b": candidato["parametros_b"],
        "quantizacao": candidato["quantizacao"],
        "timeout_s": inner.timeout_s,
        "carga_s": carga_s,
        "vram_bytes": vram_bytes,
        "capabilities": capabilities,
        "visao_local": tem_visao,
    }

    cliente = ClienteInstrumentado(inner)
    for etapa in pendentes:
        print(f"  etapa {etapa}...")
        if etapa == "roteador":
            envelope["itens"][etapa] = await etapa_roteador(cliente, external_client)
        elif etapa == "rag":
            envelope["itens"][etapa] = await etapa_rag(cliente, rag_client, external_client)
        elif etapa == "injecao":
            envelope["itens"][etapa] = await etapa_injecao(cliente, external_client)
        else:
            envelope["itens"][etapa] = await etapa_imagem(inner, tem_visao)
        consolidar_metricas(envelope)
        caminho = gravar_envelope(candidato, envelope)
        print(f"    gravado em {caminho.relative_to(EVAL_DIR.parent)}")

    # Libera a VRAM antes do próximo candidato: em 16GB, dois modelos de 12-14B
    # residentes ao mesmo tempo derrubam o segundo por falta de memória.
    await inner.unload()


def _formatar_gb(valor_bytes: int | None) -> str:
    return f"{valor_bytes / 1e9:.1f}GB" if valor_bytes else "?"


def _construir_rag_client(settings):
    qdrant = QdrantRAGClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        timeout_s=settings.qdrant_timeout_s,
        search_domain_fallback=settings.rag_search_domain_fallback,
    )
    session_factory = create_session_factory(create_db_engine(settings.postgres_dsn))
    return ActiveCollectionRagClient(qdrant, session_factory, EmbedderRegistry())


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modelos", help="ids separados por vírgula (padrão: todos)")
    parser.add_argument(
        "--etapas",
        default=",".join(ETAPAS),
        help=f"etapas separadas por vírgula (padrão: {','.join(ETAPAS)})",
    )
    parser.add_argument("--forcar", action="store_true", help="refaz etapas já gravadas")
    parser.add_argument("--timeout-s", type=float, default=TIMEOUT_PADRAO_S)
    parser.add_argument("--listar", action="store_true", help="só mostra o estado e sai")
    args = parser.parse_args()

    etapas = [e.strip() for e in args.etapas.split(",") if e.strip()]
    invalidas = [e for e in etapas if e not in ETAPAS]
    if invalidas:
        raise SystemExit(f"etapa(s) inválida(s): {', '.join(invalidas)}. Use: {', '.join(ETAPAS)}")

    ids = [i.strip() for i in args.modelos.split(",")] if args.modelos else None
    candidatos = carregar_candidatos(ids)
    settings = get_settings()
    baixados = await modelos_baixados(settings.local_model_base_url)

    if args.listar:
        for candidato in candidatos:
            envelope = carregar_envelope(candidato)
            prontas = sorted(envelope["itens"]) or ["-"]
            disponivel = "baixado" if candidato["ollama"] in baixados else "FALTA BAIXAR"
            print(f"{candidato['id']:<16} {disponivel:<12} etapas: {', '.join(prontas)}")
        return

    inner = OllamaClient(
        base_url=settings.local_model_base_url,
        model=settings.local_model_name,
        timeout_s=args.timeout_s,
        temperature=settings.local_llm_temperature,
        num_ctx=settings.local_llm_num_ctx,
        top_p=settings.local_llm_top_p,
        top_k=settings.local_llm_top_k,
        repeat_penalty=settings.local_llm_repeat_penalty,
        seed=settings.local_llm_seed,
    )
    external_client = OpenRouterClient(
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
    # Qdrant/Postgres só são necessários para a etapa `rag`; construir sempre
    # faria `--etapas roteador` falhar com o banco fora do ar.
    rag_client = _construir_rag_client(settings) if "rag" in etapas else None

    for candidato in candidatos:
        print(f"\n=== {candidato['rotulo']} ({candidato['ollama']}) ===")
        if candidato["ollama"] not in baixados:
            print(f"  não baixado — pulando. Para incluir: ollama pull {candidato['ollama']}")
            continue
        try:
            await rodar_modelo(candidato, etapas, args.forcar, inner, external_client, rag_client)
        except Exception as exc:  # noqa: BLE001
            # Um candidato que estoura a VRAM ou derruba o Ollama não pode
            # levar junto os que ainda não rodaram: o que já foi gravado fica
            # no arquivo dele e a rodada segue para o próximo.
            print(f"  FALHOU: {type(exc).__name__}: {exc}")
            await inner.unload()


if __name__ == "__main__":
    asyncio.run(main())
