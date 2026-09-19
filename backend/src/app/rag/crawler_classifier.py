"""Classificação de domínio de páginas crawleadas via LLM externo (R4,
Fase 2) — mesmo padrão de prompt/parsing de `app.router.classifier`, mas
devolvendo também uma confiança, usada pelo gate de auto-ingestão x fila de
revisão (ver docs/superpowers/specs/2026-09-19-crawler-paginas-design.md
§1).
"""

import json
import re
from typing import get_args

from pydantic import BaseModel, ValidationError

from app.models.rag import RagDomain
from app.router.llm_client import LLMClient

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


class PageClassification(BaseModel):
    domain: RagDomain
    confidence: float


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = _CODE_FENCE_RE.match(stripped)
    return match.group(1) if match else stripped


async def classify_page(llm_client: LLMClient, text: str) -> PageClassification:
    """Classifica o texto de uma página crawleada. Qualquer falha de parse
    do JSON devolvido pelo LLM (ou `domain` fora de `RagDomain`) vira
    `confidence=0.0` — nunca assume confiança alta por omissão; o `domain`
    de fallback é só um placeholder (a página cai na fila de revisão, onde
    o domain é editável antes de aprovar)."""
    prompt = _PROMPT_TEMPLATE.format(texto=text[:_MAX_PROMPT_CHARS])
    response = await llm_client.generate(prompt)
    try:
        parsed = json.loads(_strip_code_fence(response.text))
        return PageClassification(**parsed)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return PageClassification(domain=_FALLBACK_DOMAIN, confidence=0.0)
