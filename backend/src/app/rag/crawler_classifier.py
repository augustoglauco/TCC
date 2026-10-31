"""Classificação de domínio de páginas crawleadas via LLM externo (R4,
Fase 2) — mesmo padrão de prompt/parsing de `app.router.classifier`, mas
devolvendo também uma confiança, usada pelo gate de auto-ingestão x fila de
revisão (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md
§1).
"""

import asyncio
import json
import re
from typing import get_args

import httpx
from pydantic import BaseModel, ValidationError

from app.background_tasks import spawn_background_task
from app.models.rag import RagDomain
from app.router.llm_client import LLMClient, LLMResponse
from app.services.ai_usage import registrar_uso_ia

_PROMPT_TEMPLATE = """\
Classifique o conteúdo de uma página de site em UM dos domínios: vendas, \
suporte, atendimento. Avalie também sua confiança nessa classificação, de \
0.0 (nenhuma certeza) a 1.0 (certeza total).

Conteúdo da página:
{texto}

Responda apenas com JSON no formato: {{"domain": "...", "confidence": 0.0}}"""

# MVP: corte simples do texto extraído da página inteira antes de enviar ao
# LLM — a classificação é por página, não por chunk (sem chunking prévio
# aqui, diferente do pipeline de ingestão em si).
_MAX_PROMPT_CHARS = 4000

_CODE_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?(.*?)\n?```$", re.DOTALL)

_FALLBACK_DOMAIN: RagDomain = get_args(RagDomain)[0]

# O modelo externo é um tier `:free` do OpenRouter, que devolve 429 em rajadas;
# um crawl de dezenas de páginas batia nele e perdia as páginas como "erro"
# (achado de 2026-10-31 em controlid.com.br/suporte/manual_rhid). Recuo
# exponencial 2, 4, 8, 16s em 429/5xx/timeout.
_MAX_TENTATIVAS = 5
_ESPERA_BASE_S = 2.0
_STATUS_TRANSITORIOS = {429, 500, 502, 503, 504}


class PageClassification(BaseModel):
    domain: RagDomain
    confidence: float


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


def _erro_transitorio(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _STATUS_TRANSITORIOS
    return isinstance(exc, httpx.TimeoutException)


async def _gerar_com_retry(llm_client: LLMClient, prompt: str) -> LLMResponse | None:
    """Repete em erro transitório; `None` se esgotar as tentativas ou o erro não
    for transitório (o chamador trata como confiança 0)."""
    for tentativa in range(_MAX_TENTATIVAS):
        try:
            return await llm_client.generate(prompt)
        except httpx.HTTPError as exc:
            if not _erro_transitorio(exc):
                return None
            if tentativa < _MAX_TENTATIVAS - 1:
                await asyncio.sleep(_ESPERA_BASE_S * 2**tentativa)
    return None


async def classify_page(
    llm_client: LLMClient,
    text: str,
    source_identifier: str | None = None,
) -> PageClassification:
    """Classifica o texto de uma página crawleada. Qualquer falha de parse
    do JSON devolvido pelo LLM (ou `domain` fora de `RagDomain`) vira
    `confidence=0.0` — nunca assume confiança alta por omissão; o `domain`
    de fallback é só um placeholder (a página cai na fila de revisão, onde
    o domain é editável antes de aprovar). O mesmo vale quando o LLM não
    responde (429/5xx/timeout esgotados): o LLM só sugere o domínio, então a
    página não se perde."""
    prompt = _PROMPT_TEMPLATE.format(texto=text[:_MAX_PROMPT_CHARS])
    response = await _gerar_com_retry(llm_client, prompt)
    if response is None:
        return PageClassification(domain=_FALLBACK_DOMAIN, confidence=0.0)

    # Telemetria de uso de IA no ledger unificado (item E, 2026-10-08).
    # Antes escrevia em `IngestionCostEvent` via `record_ingestion_cost`;
    # era o último ponto de uso de IA fora do ledger, e o painel
    # `/admin/metricas` passou a ler só `ai_usage_events`.
    # `None` = não capturado, nunca um zero fabricado (semântica dos itens
    # A/B/D) — por isso `getattr(..., None)` sem `or 0`.
    # MVP: `ambiente="externo"` fixo porque `app.api.crawler` sempre passa
    # `app.state.external_client`; se o crawler passar a aceitar modelo
    # local, isto precisa virar parâmetro.
    spawn_background_task(
        registrar_uso_ia(
            origem="admin",
            ambiente="externo",
            modelo=getattr(response, "model_name", None)
            or getattr(llm_client, "model", None)
            or "desconhecido",
            operacao="classificacao_crawler",
            tokens_entrada=getattr(response, "prompt_tokens", None),
            tokens_saida=getattr(response, "completion_tokens", None),
            custo_usd=getattr(response, "estimated_cost_usd", None),
            referencia_id=source_identifier,
            session=None,
            session_factory=None,
            commit=False,
        )
    )

    try:
        parsed = json.loads(_strip_code_fence(response.text))
        return PageClassification(**parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):  # fmt: skip
        return PageClassification(domain=_FALLBACK_DOMAIN, confidence=0.0)
