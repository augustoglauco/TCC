"""Endpoints HTTP do gerenciador de modelos locais (Ollama, além do MVP) —
listar, ativar em runtime e baixar (biblioteca do Ollama ou GGUF do
Hugging Face) sem bloquear o backend. Ver
docs/superpowers/specs/2026-09-16-local-model-manager-design.md.

# MVP: sem autenticação — e aqui o raio de ação é maior que o de
`/admin/ingestao` (upload de arquivo limitado): `/pull` faz o SERVIDOR
buscar, de uma referência de registry informada pelo caller, um payload
arbitrário e não limitado (múltiplos GB), sem cap de tamanho, sem rate
limit e sem cap de concorrência além do dedupe por nome já existente —
risco de esgotar disco, e o `name` pode apontar para qualquer host de
registry (não só a lib do Ollama ou `hf.co`). Não expor além de
localhost sem adicionar limites reais antes.
Modelo ativo só em memória (`OllamaClient.model`) — não substitui nem
antecipa a Fase 10 (escolha de produção via benchmark offline, ver
docs/ROADMAP.md). Trocar o modelo ativo em runtime não descarrega o
anterior da VRAM — o Ollama mantém cada modelo residente pela janela de
`keep_alive` (padrão 5 min), então no alvo de GPU única de 16GB
(contenção já sinalizada em `docs/ARCHITECTURE.md` §7 para STT/chat) uma
troca logo antes de uma demo pode deixar dois modelos de chat e o
Whisper residentes ao mesmo tempo.
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

# Referência forte às tarefas de download em background — asyncio só
# guarda uma referência fraca a uma Task criada via `create_task`, o que
# arrisca ela ser coletada pelo GC no meio da execução se nada mais a
# referenciar. `add_done_callback` remove a tarefa do set assim que ela
# termina (sucesso ou erro), então o set só cresce enquanto há downloads
# genuinamente em andamento.
_background_tasks: set[asyncio.Task] = set()


def get_ollama_client(request: Request) -> OllamaClient:
    return request.app.state.local_client


def get_pull_progress_store(request: Request) -> dict[str, dict]:
    return request.app.state.model_pull_progress


async def _consumir_pull(ollama: OllamaClient, name: str, progress_store: dict[str, dict]) -> None:
    """Roda em background (`asyncio.create_task`) — nunca é aguardada pela
    requisição HTTP que a disparou. Atualiza `progress_store[name]` a cada
    linha do stream; `percent` é o da camada em download no momento, não
    agregado do modelo inteiro (ver spec §2)."""
    sucesso_confirmado = False
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
            if linha.status == "success":
                sucesso_confirmado = True
            percent = None
            if linha.total and linha.completed is not None:
                percent = (linha.completed / linha.total) * 100
            atual = progress_store.get(name, {})
            progress_store[name] = {
                "status": "pulling",
                "percent": percent if percent is not None else atual.get("percent"),
                "detail": linha.status,
            }
        if sucesso_confirmado:
            progress_store[name] = {"status": "done", "percent": 100.0, "detail": "concluído"}
            logger.info("local_model_pull_concluido nome=%s", name)
        else:
            progress_store[name] = {
                "status": "error",
                "percent": None,
                "detail": "Conexão encerrada antes da confirmação de sucesso pelo Ollama.",
            }
            logger.warning("local_model_pull_sem_confirmacao nome=%s", name)
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
    progress_store: dict[str, dict] = Depends(get_pull_progress_store),
) -> dict:
    atual = progress_store.get(body.name)
    if atual is not None and atual.get("status") == "pulling":
        return {"name": body.name}

    progress_store[body.name] = {"status": "pulling", "percent": None, "detail": "iniciando..."}
    task = asyncio.create_task(_consumir_pull(ollama, body.name, progress_store))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"name": body.name}


@router.get("/pull-status", response_model=PullStatusResponse)
async def pull_status_endpoint(
    name: str,
    progress_store: dict[str, dict] = Depends(get_pull_progress_store),
) -> PullStatusResponse:
    estado = progress_store.get(name)
    if estado is None:
        raise HTTPException(
            status_code=404, detail="Nenhum download iniciado para esse modelo."
        )
    return PullStatusResponse(**estado)
