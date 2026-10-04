"""Busca e cache de características de modelo (multimodalidade, contexto,
specs) em três fontes externas — ver docs/superpowers/specs/2026-10-03-
caracteristicas-modelo-hover-design.md.

# MVP: cada fonte tem seu próprio fetcher best-effort (nunca lança exceção
# até o chamador — falha vira `None`); a persistência/staleness fica em
# `get_or_fetch`, adicionada nas próximas tasks deste plano.
"""

import time
from datetime import timedelta
from typing import Any

import httpx

from app.models.model_catalog import (
    ModelSource,  # noqa: F401 — re-exportado (ver interface da task)
)

STALENESS = timedelta(days=7)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_OPENROUTER_CACHE_TTL_S = 3600  # 1h — ver spec §2 (lista de 466 modelos não muda a cada minuto)

# Cache em memória do processo da lista completa do OpenRouter — evita
# rebaixar ~466 modelos a cada tag diferente pedida em sequência.
_openrouter_cache: dict[str, Any] = {"models": None, "fetched_at": None}


async def _get_openrouter_catalog(http_client: httpx.AsyncClient) -> list[dict] | None:
    agora = time.monotonic()
    cache_valido = (
        _openrouter_cache["models"] is not None
        and _openrouter_cache["fetched_at"] is not None
        and (agora - _openrouter_cache["fetched_at"]) < _OPENROUTER_CACHE_TTL_S
    )
    if cache_valido:
        return _openrouter_cache["models"]

    try:
        response = await http_client.get(OPENROUTER_MODELS_URL, timeout=10.0)
        response.raise_for_status()
        modelos = response.json().get("data", [])
    except (httpx.HTTPError, ValueError):
        # ValueError cobre json.JSONDecodeError (corpo malformado).
        return _openrouter_cache["models"]  # stale-se-houver, senão None

    _openrouter_cache["models"] = modelos
    _openrouter_cache["fetched_at"] = agora
    return modelos


async def _fetch_openrouter(tag: str, http_client: httpx.AsyncClient) -> dict[str, Any] | None:
    """`source="openrouter"` — ver docs/superpowers/specs/2026-10-03-
    caracteristicas-modelo-hover-design.md §2 (fonte 1)."""
    modelos = await _get_openrouter_catalog(http_client)
    if not modelos:
        return None

    item = next((m for m in modelos if m.get("id") == tag), None)
    if item is None:
        return None

    arquitetura = item.get("architecture") or {}
    pricing = item.get("pricing") or {}

    def _preco_por_1k(valor: str | None) -> float | None:
        if valor is None:
            return None
        try:
            return float(valor) * 1000
        except (TypeError, ValueError):
            return None

    return {
        "input_modalities": arquitetura.get("input_modalities") or ["text"],
        "output_modalities": arquitetura.get("output_modalities") or ["text"],
        "context_length": item.get("context_length"),
        "pricing_prompt_per_1k": _preco_por_1k(pricing.get("prompt")),
        "pricing_completion_per_1k": _preco_por_1k(pricing.get("completion")),
        "knowledge_cutoff": item.get("knowledge_cutoff"),
        "raw_payload": item,
    }
