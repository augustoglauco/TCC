"""Avalia a acurácia do roteador de intenção (R3, Fase 1) sobre o conjunto
de teste rotulado em `dataset.json`, para os três provedores disponíveis
(`heuristica`, `heuristica_llm`, `jev_openrouter`) — ver docs/EVALUATION.md
Seção 1.

Uso (a partir de `backend/`, com Ollama no ar e `EXTERNAL_MODEL_API_KEY`
configurada no `.env` — chama a API real do OpenRouter para o provedor
`jev_openrouter`, e o Ollama local para os casos ambíguos de
`heuristica_llm`):

    .venv/bin/python eval/router_intents/run_eval.py

Salva `eval/router_intents/results.json` com, por provedor: acurácia geral,
matriz de confusão (domínio esperado x domínio previsto — inclui
`fora_escopo` como coluna extra quando o classificador escala em vez de
decidir), latência média por chamada, contagem de degradação silenciosa
(`provider_efetivo` diferente do provedor pedido — ver aviso em
docs/EVALUATION.md sobre não contaminar a comparação) e a lista de casos
errados para inspeção qualitativa.
"""

import asyncio
import json
import time
from pathlib import Path

from app.config import get_settings
from app.router.classifier import Domain, classify
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient

_DOMINIOS: list[Domain] = ["vendas", "suporte", "atendimento", "agendamento"]
_PROVIDERS = ["heuristica", "heuristica_llm", "jev_openrouter"]

BASE_DIR = Path(__file__).parent


def _carregar_casos() -> list[dict]:
    dados = json.loads((BASE_DIR / "dataset.json").read_text(encoding="utf-8"))
    return dados["casos"]


async def _avaliar_provider(
    provider: str, casos: list[dict], local_client, external_client
) -> dict:
    matriz: dict[str, dict[str, int]] = {esperado: {} for esperado in _DOMINIOS}
    erros = []
    degradacoes = []
    latencias = []
    acertos = 0

    # `classify()` só chama de fato o LLM local para provider="heuristica_llm"
    # quando `strategy="llm"` também é passado — mesma lógica de
    # `efetiva_complexity_strategy` em `app.api.chat` (achado ao rodar esta
    # avaliação: sem isso, heuristica_llm silenciosamente nunca sai da
    # heurística pura, produzindo resultado idêntico a provider="heuristica").
    strategy = "llm" if provider == "heuristica_llm" else "heuristic"

    for caso in casos:
        inicio = time.perf_counter()
        resultado = await classify(
            caso["mensagem"],
            recent_messages=[],
            strategy=strategy,
            llm_client=local_client,
            provider=provider,
            external_client=external_client,
        )
        latencias.append(time.perf_counter() - inicio)

        esperado = caso["intencao_esperada"]
        previsto = resultado.domain
        matriz[esperado][previsto] = matriz[esperado].get(previsto, 0) + 1

        if resultado.provider_efetivo != provider:
            degradacoes.append({"id": caso["id"], "provider_efetivo": resultado.provider_efetivo})

        if previsto == esperado:
            acertos += 1
        else:
            erros.append(
                {
                    "id": caso["id"],
                    "mensagem": caso["mensagem"],
                    "esperado": esperado,
                    "previsto": previsto,
                    "ambiguo": caso.get("ambiguo", False),
                    "provider_efetivo": resultado.provider_efetivo,
                }
            )

    total = len(casos)
    return {
        "provider": provider,
        "acuracia": round(acertos / total, 4),
        "acertos": acertos,
        "total": total,
        "latencia_media_s": round(sum(latencias) / len(latencias), 3),
        "degradacoes_de_provider": degradacoes,
        "matriz_confusao": matriz,
        "erros": erros,
    }


async def main() -> None:
    settings = get_settings()
    casos = _carregar_casos()

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

    resultados = {}
    for provider in _PROVIDERS:
        print(f"Avaliando provider={provider} ({len(casos)} casos)...")
        resultados[provider] = await _avaliar_provider(
            provider, casos, local_client, external_client
        )
        r = resultados[provider]
        print(
            f"  acurácia={r['acuracia']:.1%}  latência_média={r['latencia_media_s']:.3f}s  "
            f"degradações={len(r['degradacoes_de_provider'])}  erros={len(r['erros'])}"
        )

    output_path = BASE_DIR / "results.json"
    output_path.write_text(
        json.dumps({"dominios": _DOMINIOS, "providers": resultados}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nResultados salvos em {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
