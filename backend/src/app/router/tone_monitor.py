import json
import logging
from typing import Any

from pydantic import BaseModel

from app.models.runtime_settings import DEFAULT_TONE_MONITOR_PROVIDER
from app.router.classifier import _normalize, _strip_code_fence
from app.router.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ToneResult(BaseModel):
    escalate: bool
    motivo: str | None  # "urgencia" | "insatisfacao" | None quando escalate=False
    confidence: float
    # Mesma convenção de ClassificationResult.provider_efetivo
    # (docs/ARCHITECTURE.md §5): só distingue qual dos DOIS provedores
    # configuráveis (TONE_MONITOR_PROVIDER) decidiu de fato — falha do Jev
    # sempre degrada para "heuristica_llm", nunca derruba a mensagem do
    # usuário (ver docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3).
    provider_efetivo: str = DEFAULT_TONE_MONITOR_PROVIDER


# MVP: heurística simples de palavras-chave, mesmo espírito de
# app.router.classifier._DOMAIN_KEYWORDS — sem NLP mais robusto, lista a
# refinar contra casos reais quando existirem.
_URGENCIA_KEYWORDS = ["urgente", "agora mesmo", "imediatamente"]
_INSATISFACAO_KEYWORDS = [
    "pessimo",
    "absurdo",
    "cancelar tudo",
    "processar",
    "reclamacao procon",
    "nunca mais compro",
]

_UPPERCASE_ALPHA_MIN = 10
_UPPERCASE_RATIO_THRESHOLD = 0.7
_EXCLAMATION_RUN_MIN = 3


def _match_keyword_signal(message: str) -> str | None:
    normalized = _normalize(message)
    if any(k in normalized for k in _URGENCIA_KEYWORDS):
        return "urgencia"
    if any(k in normalized for k in _INSATISFACAO_KEYWORDS):
        return "insatisfacao"
    return None


def _match_structural_signal(message: str) -> str | None:
    # Sinal estrutural (maiúsculas/pontuação) lido como urgência — não há
    # como a pontuação por si só distinguir insatisfação de urgência, ver
    # docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §3.1.
    alpha_chars = [c for c in message if c.isalpha()]
    if len(alpha_chars) >= _UPPERCASE_ALPHA_MIN:
        uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if uppercase_ratio >= _UPPERCASE_RATIO_THRESHOLD:
            return "urgencia"
    if "!" * _EXCLAMATION_RUN_MIN in message:
        return "urgencia"
    return None


def _match_heuristic_signal(message: str) -> str | None:
    return _match_keyword_signal(message) or _match_structural_signal(message)


_TONE_PROMPT_TEMPLATE = """\
Avalie se a mensagem do cliente abaixo demonstra urgência ou insatisfação \
forte o suficiente para justificar transferência a um atendente humano.

Contexto recente:
{contexto}

Mensagem atual: {mensagem}

Responda apenas com JSON no formato: \
{{"escalar": true|false, "motivo": "urgencia"|"insatisfacao"|null, "confianca": 0.0}}"""


async def _analyze_with_llm(
    message: str, recent_messages: list[str], llm_client: LLMClient
) -> ToneResult:
    contexto = "\n".join(recent_messages) if recent_messages else "(nenhum)"
    prompt = _TONE_PROMPT_TEMPLATE.format(contexto=contexto, mensagem=message)
    try:
        response = await llm_client.generate(prompt)
        parsed = json.loads(_strip_code_fence(response.text))
        escalate = bool(parsed.get("escalar", False))
        motivo = parsed.get("motivo") if escalate else None
        confidence = float(parsed.get("confianca", 0.0))
        return ToneResult(
            escalate=escalate,
            motivo=motivo,
            confidence=confidence,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        # Resposta não-parseável: ambíguo sem sinal claro não escala por
        # padrão, lado seguro contra falso positivo (mesmo espírito de
        # classifier._classify_heuristic_fallback).
        return ToneResult(
            escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
        )


async def _analyze_with_jev(
    message: str, recent_messages: list[str], external_client: Any
) -> ToneResult:
    try:
        if external_client is None or not hasattr(external_client, "classify_tone_jev"):
            raise ValueError("external_client inválido para Jev")
        escalate, confidence = await external_client.classify_tone_jev(message, recent_messages)
        # Jev responde com uma única pergunta noul (sim/não) — não distingue
        # motivo. "insatisfacao" é um rótulo genérico quando escala; refinar
        # com duas perguntas noul separadas fica para uma iteração futura.
        return ToneResult(
            escalate=escalate,
            motivo="insatisfacao" if escalate else None,
            confidence=confidence,
            provider_efetivo="jev_openrouter",
        )
    except Exception as exc:
        logger.warning(
            "jev_tom_falhou_fallback_heuristica",
            extra={"router": {"event": "jev_tom_falha_fallback", "erro": str(exc)}},
        )
        return ToneResult(
            escalate=False, motivo=None, confidence=0.0, provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER
        )


async def analyze_tone(
    message: str,
    recent_messages: list[str],
    strategy_provider: str,
    llm_client: LLMClient,
    external_client: Any,
) -> ToneResult:
    sinal = _match_heuristic_signal(message)
    if sinal is not None:
        return ToneResult(
            escalate=True,
            motivo=sinal,
            confidence=1.0,
            provider_efetivo=DEFAULT_TONE_MONITOR_PROVIDER,
        )

    if strategy_provider == "jev_openrouter":
        return await _analyze_with_jev(message, recent_messages, external_client)

    return await _analyze_with_llm(message, recent_messages, llm_client)


# MVP: estado em memória por processo, mesmo padrão de
# app.router.scheduling.booking_slots e app.api.chat._conversation_history —
# perdido em restart do processo, sem mecanismo de "des-escalar" (decisão
# aceita da spec §2).
_conversas_escaladas: set[str] = set()


def marcar_escalada(conversation_id: str) -> None:
    _conversas_escaladas.add(conversation_id)


def ja_escalada(conversation_id: str) -> bool:
    return conversation_id in _conversas_escaladas


def reset_escalated_conversations() -> None:
    """Limpa o estado em memória — usado pelos testes para isolar casos."""
    _conversas_escaladas.clear()
