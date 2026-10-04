import inspect
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verificar_admin_por_token
from app.api.rag_dependencies import get_db_session
from app.db.settings import save_multiple_app_settings
from app.models.runtime_settings import (
    DEFAULT_INTENT_ROUTER_PROVIDER,
    DEFAULT_TONE_MONITOR_PROVIDER,
    RuntimeSettingsResponse,
    RuntimeSettingsUpdateRequest,
)
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/runtime-settings", tags=["runtime-settings"])


async def _require_admin(
    session: AsyncSession = Depends(get_db_session),
    authorization: Annotated[str | None, Header()] = None,
    x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
    token_param: Annotated[str | None, Query(alias="token")] = None,
) -> None:
    token: str | None = None
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        elif len(parts) == 1:
            token = parts[0]
    elif x_auth_token:
        token = x_auth_token
    elif token_param:
        token = token_param

    if not token or not await verificar_admin_por_token(session, token):
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores autenticados.",
        )


def _get_clients(
    request: Request,
) -> tuple[OllamaClient, OpenRouterClient, QdrantRAGClient]:
    return (
        request.app.state.local_client,
        request.app.state.external_client,
        request.app.state.qdrant_client,
    )


async def _build_response(request: Request) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)
    intent_provider = getattr(
        request.app.state, "intent_router_provider", DEFAULT_INTENT_ROUTER_PROVIDER
    )
    tone_monitor_enabled = getattr(request.app.state, "tone_monitor_enabled", True)
    tone_monitor_provider = getattr(
        request.app.state, "tone_monitor_provider", DEFAULT_TONE_MONITOR_PROVIDER
    )
    rag_top_k = getattr(request.app.state, "rag_top_k", 3)
    rag_score_threshold = getattr(request.app.state, "rag_score_threshold", 0.35)
    keep_alive = str(getattr(local_client, "keep_alive", "-1"))
    warmup_on_startup = getattr(request.app.state, "local_llm_warmup_on_startup", True)

    loaded_info = None
    if hasattr(local_client, "get_loaded_status") and inspect.iscoroutinefunction(
        local_client.get_loaded_status
    ):
        try:
            loaded_info = await local_client.get_loaded_status()
        except Exception:
            pass

    local_model_loaded = loaded_info is not None
    local_model_vram_bytes = loaded_info.get("size_vram") if loaded_info else None

    return RuntimeSettingsResponse(
        local_llm_temperature=local_client.temperature,
        local_llm_num_ctx=local_client.num_ctx,
        local_llm_top_p=local_client.top_p,
        local_llm_top_k=local_client.top_k,
        local_llm_repeat_penalty=local_client.repeat_penalty,
        local_llm_seed=local_client.seed,
        local_llm_timeout_s=local_client.timeout_s,
        external_llm_timeout_s=external_client.timeout_s,
        rag_top_k=rag_top_k,
        rag_score_threshold=rag_score_threshold,
        rag_search_domain_fallback=qdrant_client.search_domain_fallback,
        crawler_max_pages_default=request.app.state.crawler_max_pages_default,
        crawler_confidence_threshold=request.app.state.crawler_confidence_threshold,
        external_model_name=external_client.model,
        external_vision_model_name=external_client.vision_model,
        image_internal_confidence=request.app.state.image_internal_confidence,
        image_external_confidence=request.app.state.image_external_confidence,
        intent_router_provider=intent_provider,
        tone_monitor_enabled=tone_monitor_enabled,
        tone_monitor_provider=tone_monitor_provider,
        local_llm_keep_alive=keep_alive,
        local_llm_warmup_on_startup=warmup_on_startup,
        local_model_loaded=local_model_loaded,
        local_model_vram_bytes=local_model_vram_bytes,
    )


@router.get("", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(
    request: Request, _: None = Depends(_require_admin)
) -> RuntimeSettingsResponse:
    return await _build_response(request)


@router.put("", response_model=RuntimeSettingsResponse)
async def update_runtime_settings(
    request: Request,
    body: RuntimeSettingsUpdateRequest,
    _: None = Depends(_require_admin),
) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)

    campos = body.model_dump(exclude_unset=True)

    if "local_llm_temperature" in campos:
        local_client.temperature = campos["local_llm_temperature"]
    if "local_llm_num_ctx" in campos:
        local_client.num_ctx = campos["local_llm_num_ctx"]
    if "local_llm_top_p" in campos:
        local_client.top_p = campos["local_llm_top_p"]
    if "local_llm_top_k" in campos:
        local_client.top_k = campos["local_llm_top_k"]
    if "local_llm_repeat_penalty" in campos:
        local_client.repeat_penalty = campos["local_llm_repeat_penalty"]
    if "local_llm_seed" in campos:
        local_client.seed = campos["local_llm_seed"]
    if "local_llm_timeout_s" in campos:
        local_client.timeout_s = campos["local_llm_timeout_s"]
    if "external_llm_timeout_s" in campos:
        external_client.timeout_s = campos["external_llm_timeout_s"]
    if "rag_top_k" in campos:
        request.app.state.rag_top_k = campos["rag_top_k"]
    if "rag_score_threshold" in campos:
        request.app.state.rag_score_threshold = campos["rag_score_threshold"]
    if "rag_search_domain_fallback" in campos:
        qdrant_client.search_domain_fallback = campos["rag_search_domain_fallback"]
    if "crawler_max_pages_default" in campos:
        request.app.state.crawler_max_pages_default = campos["crawler_max_pages_default"]
    if "crawler_confidence_threshold" in campos:
        request.app.state.crawler_confidence_threshold = campos["crawler_confidence_threshold"]
    if "external_model_name" in campos:
        external_client.model = campos["external_model_name"]
    if "external_vision_model_name" in campos:
        external_client.vision_model = campos["external_vision_model_name"]
    if "image_internal_confidence" in campos:
        request.app.state.image_internal_confidence = campos["image_internal_confidence"]
    if "image_external_confidence" in campos:
        request.app.state.image_external_confidence = campos["image_external_confidence"]
    if "intent_router_provider" in campos:
        request.app.state.intent_router_provider = campos["intent_router_provider"]
    if "tone_monitor_enabled" in campos:
        request.app.state.tone_monitor_enabled = campos["tone_monitor_enabled"]
    if "tone_monitor_provider" in campos:
        request.app.state.tone_monitor_provider = campos["tone_monitor_provider"]
    if "local_llm_keep_alive" in campos:
        local_client.keep_alive = campos["local_llm_keep_alive"]
        if hasattr(local_client, "preload") and inspect.iscoroutinefunction(local_client.preload):
            try:
                if str(campos["local_llm_keep_alive"]) == "0":
                    await local_client.unload()
                else:
                    await local_client.preload()
            except Exception as exc:
                logger.warning("Falha ao sincronizar keep_alive no Ollama: %s", exc)
    if "local_llm_warmup_on_startup" in campos:
        request.app.state.local_llm_warmup_on_startup = campos["local_llm_warmup_on_startup"]

    # Persistência no PostgreSQL
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if session_factory is not None and campos:
        try:
            async with session_factory() as session:
                await save_multiple_app_settings(session, campos)
        except Exception as exc:
            logger.warning("Falha ao persistir runtime settings no banco: %s", exc)

    return await _build_response(request)


@router.post("/preload", response_model=RuntimeSettingsResponse)
async def preload_local_model(
    request: Request, _: None = Depends(_require_admin)
) -> RuntimeSettingsResponse:
    """Carrega o modelo local na VRAM imediatamente (warmup manual)."""
    local_client, _, _ = _get_clients(request)
    if hasattr(local_client, "preload") and inspect.iscoroutinefunction(local_client.preload):
        await local_client.preload()
    return await _build_response(request)


@router.post("/unload", response_model=RuntimeSettingsResponse)
async def unload_local_model(
    request: Request, _: None = Depends(_require_admin)
) -> RuntimeSettingsResponse:
    """Descarrega o modelo local da VRAM imediatamente (libera memória)."""
    local_client, _, _ = _get_clients(request)
    if hasattr(local_client, "unload") and inspect.iscoroutinefunction(local_client.unload):
        await local_client.unload()
    return await _build_response(request)
