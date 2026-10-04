"""Busca e cache de características de modelo (multimodalidade, contexto,
specs) em três fontes externas — ver docs/superpowers/specs/2026-10-03-
caracteristicas-modelo-hover-design.md.

# MVP: cada fonte tem seu próprio fetcher best-effort (nunca lança exceção
# até o chamador — falha vira `None`); a persistência/staleness/upsert fica
# em `get_or_fetch`, que orquestra os três fetchers via Postgres.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ModelCharacteristics
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


def _context_length_do_model_info(model_info: dict[str, Any]) -> int | None:
    for chave, valor in model_info.items():
        if chave.endswith(".context_length") and isinstance(valor, int):
            return valor
    return None


async def _fetch_ollama(tag: str, ollama_client: Any) -> dict[str, Any] | None:
    """`source="ollama"` — só funciona para modelo já baixado (`/api/show`
    não existe para modelos não baixados). Ver spec §2 (fonte 2).
    `ollama_client` é duck-typed (`OllamaClient`, precisa de
    `get_model_details(name) -> dict | None`)."""
    detalhes = await ollama_client.get_model_details(tag)
    if detalhes is None:
        return None

    capabilities = detalhes.get("capabilities") or []
    input_modalities = ["text", "image"] if "vision" in capabilities else ["text"]
    details = detalhes.get("details") or {}
    model_info = detalhes.get("model_info") or {}

    return {
        "input_modalities": input_modalities,
        "output_modalities": ["text"],
        "context_length": _context_length_do_model_info(model_info),
        "parameter_size": details.get("parameter_size"),
        "quantization": details.get("quantization_level"),
        "pricing_prompt_per_1k": None,
        "pricing_completion_per_1k": None,
        "knowledge_cutoff": None,
        "raw_payload": detalhes,
    }


HUGGINGFACE_MODELS_URL = "https://huggingface.co/api/models"

PIPELINE_TAG_MODALIDADES: dict[str, tuple[list[str], list[str]]] = {
    "text-generation": (["text"], ["text"]),
    "text2text-generation": (["text"], ["text"]),
    "image-text-to-text": (["text", "image"], ["text"]),
    "visual-question-answering": (["text", "image"], ["text"]),
    "image-to-text": (["image"], ["text"]),
    "automatic-speech-recognition": (["audio"], ["text"]),
    "audio-text-to-text": (["text", "audio"], ["text"]),
    "any-to-any": (["text", "image", "audio"], ["text", "image", "audio"]),
}


def _repo_do_tag_huggingface(tag: str) -> str | None:
    if not tag.lower().startswith("hf.co/"):
        return None
    sem_prefixo = tag[len("hf.co/") :]
    return sem_prefixo.split(":", 1)[0]


async def _fetch_huggingface(tag: str, http_client: httpx.AsyncClient) -> dict[str, Any] | None:
    """`source="huggingface"` — só para tags `hf.co/<usuario>/<repo>[:quant]`
    ainda não baixadas (único caso em que nem OpenRouter nem Ollama têm
    informação). Ver spec §2 (fonte 3)."""
    repo = _repo_do_tag_huggingface(tag)
    if repo is None:
        return None

    try:
        response = await http_client.get(f"{HUGGINGFACE_MODELS_URL}/{repo}", timeout=10.0)
        response.raise_for_status()
        dados = response.json()
    except (httpx.HTTPError, ValueError):
        # ValueError cobre json.JSONDecodeError (corpo malformado).
        return None

    pipeline_tag = dados.get("pipeline_tag")
    input_modalities, output_modalities = PIPELINE_TAG_MODALIDADES.get(
        pipeline_tag, (["desconhecido"], ["desconhecido"])
    )

    return {
        "input_modalities": input_modalities,
        "output_modalities": output_modalities,
        "context_length": None,
        "parameter_size": None,
        "quantization": None,
        "pricing_prompt_per_1k": None,
        "pricing_completion_per_1k": None,
        "knowledge_cutoff": None,
        "raw_payload": dados,
    }


_FETCHERS = {
    "openrouter": lambda tag, ollama_client, http_client: _fetch_openrouter(tag, http_client),
    "ollama": lambda tag, ollama_client, http_client: _fetch_ollama(tag, ollama_client),
    "huggingface": lambda tag, ollama_client, http_client: _fetch_huggingface(tag, http_client),
}


async def _buscar_linha(
    session: AsyncSession, source: str, tag: str
) -> ModelCharacteristics | None:
    result = await session.execute(
        select(ModelCharacteristics).where(
            ModelCharacteristics.source == source, ModelCharacteristics.tag == tag
        )
    )
    return result.scalars().first()


def _esta_fresco(linha: ModelCharacteristics) -> bool:
    fetched_at = linha.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    return (datetime.now(UTC) - fetched_at) < STALENESS


async def get_or_fetch(
    session: AsyncSession,
    source: ModelSource,
    tag: str,
    *,
    force_refresh: bool = False,
    ollama_client: Any = None,
    http_client: httpx.AsyncClient | None = None,
) -> ModelCharacteristics | None:
    """Cache-first: devolve a linha do Postgres se fresca (< 7 dias); senão
    busca na fonte (`_FETCHERS[source]`) e faz upsert. `force_refresh=True`
    ignora a frescura e sempre busca de novo. Falha na busca com uma linha
    stale existente → serve a stale (nunca quebra a tela); falha sem
    nenhuma linha → `None`. Ver spec §2."""
    linha_existente = await _buscar_linha(session, source, tag)

    if linha_existente is not None and not force_refresh and _esta_fresco(linha_existente):
        return linha_existente

    dados = await _FETCHERS[source](tag, ollama_client, http_client)

    if dados is None:
        return linha_existente  # stale-se-houver, senão None

    is_multimodal = len(set(dados["input_modalities"]) - {"text"}) > 0

    if linha_existente is not None:
        for campo, valor in dados.items():
            setattr(linha_existente, campo, valor)
        linha_existente.is_multimodal = is_multimodal
        linha_existente.fetched_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(linha_existente)
        return linha_existente

    nova_linha = ModelCharacteristics(source=source, tag=tag, is_multimodal=is_multimodal, **dados)
    session.add(nova_linha)
    await session.commit()
    await session.refresh(nova_linha)
    return nova_linha
