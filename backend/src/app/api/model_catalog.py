"""Endpoints HTTP das características de modelo (multimodalidade, contexto,
specs) — ver docs/superpowers/specs/2026-10-03-caracteristicas-modelo-
hover-design.md.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.model_catalog.characteristics import get_or_fetch
from app.models.model_catalog import (
    CharacteristicsRefreshRequest,
    ModelCharacteristicsResponse,
    ModelSource,
)
from app.router.ollama_client import OllamaClient

router = APIRouter(prefix="/api/admin/model-catalog", tags=["model-catalog"])


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.local_client


def get_model_catalog_http_client(request: Request):
    return request.app.state.model_catalog_http_client


def _to_response(linha) -> ModelCharacteristicsResponse:
    return ModelCharacteristicsResponse(
        source=linha.source,
        tag=linha.tag,
        is_multimodal=linha.is_multimodal,
        input_modalities=linha.input_modalities,
        output_modalities=linha.output_modalities,
        context_length=linha.context_length,
        parameter_size=linha.parameter_size,
        quantization=linha.quantization,
        pricing_prompt_per_1k=linha.pricing_prompt_per_1k,
        pricing_completion_per_1k=linha.pricing_completion_per_1k,
        knowledge_cutoff=linha.knowledge_cutoff,
        fetched_at=linha.fetched_at,
    )


@router.get("/characteristics", response_model=ModelCharacteristicsResponse)
async def get_characteristics(
    source: ModelSource,
    tag: str,
    session: AsyncSession = Depends(get_db_session),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    http_client=Depends(get_model_catalog_http_client),
):
    linha = await get_or_fetch(
        session, source, tag, ollama_client=ollama_client, http_client=http_client
    )
    if linha is None:
        raise HTTPException(404, detail=f"Características não encontradas para {source}:{tag}.")
    return _to_response(linha)


@router.post("/characteristics/refresh", response_model=ModelCharacteristicsResponse)
async def refresh_characteristics(
    payload: CharacteristicsRefreshRequest,
    session: AsyncSession = Depends(get_db_session),
    ollama_client: OllamaClient = Depends(get_ollama_client),
    http_client=Depends(get_model_catalog_http_client),
):
    linha = await get_or_fetch(
        session,
        payload.source,
        payload.tag,
        force_refresh=True,
        ollama_client=ollama_client,
        http_client=http_client,
    )
    if linha is None:
        raise HTTPException(
            404, detail=f"Características não encontradas para {payload.source}:{payload.tag}."
        )
    return _to_response(linha)
