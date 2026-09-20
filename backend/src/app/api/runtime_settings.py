"""Endpoint HTTP dos parâmetros de execução ajustáveis em runtime (além do
MVP) — temperatura do Ollama, timeouts dos backends local/externo, a flag
de fallback de domínio do RAG, e o teto default/limiar de confiança do
crawler de páginas. Mesmo padrão do gerenciador de modelos locais
(`app.api.local_models`): valores só em memória (`request.app.state.*`),
resetam a cada restart do processo. Ver decisão registrada em
docs/ARCHITECTURE.md §5.
"""

from fastapi import APIRouter, Request

from app.models.runtime_settings import RuntimeSettingsResponse, RuntimeSettingsUpdateRequest
from app.rag.qdrant_client import QdrantRAGClient
from app.router.ollama_client import OllamaClient
from app.router.openrouter_client import OpenRouterClient

router = APIRouter(prefix="/api/admin/runtime-settings", tags=["runtime-settings"])


def _get_clients(
    request: Request,
) -> tuple[OllamaClient, OpenRouterClient, QdrantRAGClient]:
    return (
        request.app.state.local_client,
        request.app.state.external_client,
        request.app.state.qdrant_client,
    )


def _build_response(request: Request) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)
    return RuntimeSettingsResponse(
        local_llm_temperature=local_client.temperature,
        local_llm_timeout_s=local_client.timeout_s,
        external_llm_timeout_s=external_client.timeout_s,
        rag_search_domain_fallback=qdrant_client.search_domain_fallback,
        crawler_max_pages_default=request.app.state.crawler_max_pages_default,
        crawler_confidence_threshold=request.app.state.crawler_confidence_threshold,
        external_vision_model_name=external_client.vision_model,
        image_internal_confidence=request.app.state.image_internal_confidence,
        image_external_confidence=request.app.state.image_external_confidence,
    )


@router.get("", response_model=RuntimeSettingsResponse)
async def get_runtime_settings(request: Request) -> RuntimeSettingsResponse:
    return _build_response(request)


@router.put("", response_model=RuntimeSettingsResponse)
async def update_runtime_settings(
    request: Request, body: RuntimeSettingsUpdateRequest
) -> RuntimeSettingsResponse:
    local_client, external_client, qdrant_client = _get_clients(request)

    # `exclude_unset` distingue "campo não enviado" (não mexe) de "campo
    # enviado com valor, inclusive null" (aplica) — permite ao cliente
    # voltar `local_llm_temperature` para `null` (usa o default do próprio
    # modelo) mandando o campo explicitamente, sem afetar os demais campos
    # não enviados nesta chamada.
    campos = body.model_dump(exclude_unset=True)

    if "local_llm_temperature" in campos:
        local_client.temperature = campos["local_llm_temperature"]
    if "local_llm_timeout_s" in campos:
        local_client.timeout_s = campos["local_llm_timeout_s"]
    if "external_llm_timeout_s" in campos:
        external_client.timeout_s = campos["external_llm_timeout_s"]
    if "rag_search_domain_fallback" in campos:
        qdrant_client.search_domain_fallback = campos["rag_search_domain_fallback"]
    if "crawler_max_pages_default" in campos:
        request.app.state.crawler_max_pages_default = campos["crawler_max_pages_default"]
    if "crawler_confidence_threshold" in campos:
        request.app.state.crawler_confidence_threshold = campos["crawler_confidence_threshold"]
    if "external_vision_model_name" in campos:
        external_client.vision_model = campos["external_vision_model_name"]
    if "image_internal_confidence" in campos:
        request.app.state.image_internal_confidence = campos["image_internal_confidence"]
    if "image_external_confidence" in campos:
        request.app.state.image_external_confidence = campos["image_external_confidence"]

    return _build_response(request)
