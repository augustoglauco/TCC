"""Endpoint HTTP do chat (R2, R3) — encaminha para o orchestrator do roteador."""

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.chat import ChatMessageRequest, ChatMessageResponse
from app.router.llm_client import LLMClient
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    handle_message,
)
from app.router.rag_client import RAGClient, RAGConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

_MAX_HISTORY_MESSAGES = 3

# MVP: histórico de conversa mantido em memória por processo (dict simples
# `conversation_id -> últimas mensagens`) — sem persistência em banco nem
# resumo automático, que ficam para a Fase 6 (R9, ver docs/ROADMAP.md). O
# histórico também não sobrevive a um restart do processo.
_conversation_history: dict[str, list[str]] = {}


def reset_conversation_history() -> None:
    """Limpa o histórico em memória — usado pelos testes para isolar casos."""
    _conversation_history.clear()


def get_local_client(request: Request) -> LLMClient:
    return request.app.state.local_client


def get_external_client(request: Request) -> LLMClient:
    return request.app.state.external_client


def get_rag_client(request: Request) -> RAGClient:
    return request.app.state.rag_client


def get_complexity_strategy(request: Request) -> str:
    return request.app.state.complexity_strategy


@router.post("/messages", response_model=ChatMessageResponse)
async def send_message(
    payload: ChatMessageRequest,
    local_client: LLMClient = Depends(get_local_client),
    external_client: LLMClient = Depends(get_external_client),
    rag_client: RAGClient = Depends(get_rag_client),
    complexity_strategy: str = Depends(get_complexity_strategy),
) -> ChatMessageResponse:
    conversation_id = payload.conversation_id or str(uuid4())
    recent_messages = list(_conversation_history.get(conversation_id, []))

    # `payload.audio` é intencionalmente ignorado aqui — ver comentário MVP
    # em `app.models.chat.ChatMessageRequest.audio`.
    try:
        decision = await handle_message(
            message=payload.message,
            recent_messages=recent_messages,
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy=complexity_strategy,
        )
    except (
        LocalBackendIndisponivelError,
        ExternalBackendIndisponivelError,
        RAGConnectionError,
    ) as exc:
        logger.error(
            "chat_dependencia_indisponivel",
            extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
        )
        raise HTTPException(
            status_code=503, detail="Serviço temporariamente indisponível, tente novamente."
        ) from exc

    history = _conversation_history.setdefault(conversation_id, [])
    history.append(payload.message)
    del history[:-_MAX_HISTORY_MESSAGES]

    return ChatMessageResponse(
        conversation_id=conversation_id,
        message=decision.resposta,
        domain=decision.domain,
        backend_used=decision.backend_escolhido,
        escalation_reason=decision.motivo_escalonamento,
    )
