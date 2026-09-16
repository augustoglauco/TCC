"""Endpoints HTTP do gerenciador de modelos locais (Ollama, além do MVP) —
listar, ativar em runtime e baixar (biblioteca do Ollama ou GGUF do
Hugging Face) sem bloquear o backend. Ver
docs/superpowers/specs/2026-09-16-local-model-manager-design.md.

# MVP: sem autenticação (mesma limitação já aceita para `/admin/ingestao`).
Modelo ativo só em memória (`OllamaClient.model`) — não substitui nem
antecipa a Fase 10 (escolha de produção via benchmark offline, ver
docs/ROADMAP.md).
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.local_models import (
    ActivateModelRequest,
    LocalModelResponse,
    LocalModelsListResponse,
    PullModelRequest,
    PullStatusResponse,
)
from app.router.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/local-models", tags=["local-models"])


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.local_client


def get_pull_progress_store(request: Request) -> dict:
    return request.app.state.model_pull_progress


async def _consumir_pull(ollama: OllamaClient, name: str, progress_store: dict) -> None:
    """Roda em background (`asyncio.create_task`) — nunca é aguardada pela
    requisição HTTP que a disparou. Atualiza `progress_store[name]` a cada
    linha do stream; `percent` é o da camada em download no momento, não
    agregado do modelo inteiro (ver spec §2)."""
    try:
        async for linha in ollama.pull_model_streaming(name):
            if linha.error:
                progress_store[name] = {
                    "status": "error",
                    "percent": None,
                    "detail": linha.error,
                }
                logger.warning(
                    "local_model_pull_erro nome=%s erro=%s", name, linha.error
                )
                return
            percent = None
            if linha.total and linha.completed is not None:
                percent = (linha.completed / linha.total) * 100
            atual = progress_store.get(name, {})
            progress_store[name] = {
                "status": "pulling",
                "percent": percent if percent is not None else atual.get("percent"),
                "detail": linha.status,
            }
        progress_store[name] = {"status": "done", "percent": 100.0, "detail": "concluído"}
        logger.info("local_model_pull_concluido nome=%s", name)
    except Exception as exc:
        progress_store[name] = {"status": "error", "percent": None, "detail": str(exc)}
        logger.warning("local_model_pull_erro nome=%s erro=%s", name, exc)


@router.get("", response_model=LocalModelsListResponse)
async def list_local_models_endpoint(
    ollama: OllamaClient = Depends(get_ollama_client),
) -> LocalModelsListResponse:
    modelos = await ollama.list_local_models()
    ativo = ollama.model
    return LocalModelsListResponse(
        models=[
            LocalModelResponse(
                name=modelo.name,
                size_bytes=modelo.size_bytes,
                modified_at=modelo.modified_at,
                is_active=(modelo.name == ativo),
            )
            for modelo in modelos
        ],
        active_model=ativo,
    )


@router.post("/activate", status_code=204)
async def activate_model_endpoint(
    body: ActivateModelRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
) -> None:
    modelos = await ollama.list_local_models()
    if body.name not in {modelo.name for modelo in modelos}:
        raise HTTPException(
            status_code=404, detail="Modelo não encontrado entre os já baixados."
        )
    ollama.model = body.name


@router.post("/pull", status_code=202)
async def pull_model_endpoint(
    body: PullModelRequest,
    ollama: OllamaClient = Depends(get_ollama_client),
    progress_store: dict = Depends(get_pull_progress_store),
) -> dict:
    atual = progress_store.get(body.name)
    if atual is not None and atual.get("status") == "pulling":
        return {"name": body.name}

    progress_store[body.name] = {"status": "pulling", "percent": None, "detail": "iniciando..."}
    asyncio.create_task(_consumir_pull(ollama, body.name, progress_store))
    return {"name": body.name}


@router.get("/pull-status", response_model=PullStatusResponse)
async def pull_status_endpoint(
    name: str,
    progress_store: dict = Depends(get_pull_progress_store),
) -> PullStatusResponse:
    estado = progress_store.get(name)
    if estado is None:
        raise HTTPException(
            status_code=404, detail="Nenhum download iniciado para esse modelo."
        )
    return PullStatusResponse(**estado)
