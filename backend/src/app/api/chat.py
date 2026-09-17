"""Endpoint HTTP do chat (R2, R3, R5) — encaminha para o orchestrator do roteador."""

import base64
import binascii
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.chat import ChatDoneEventData, ChatMessageRequest
from app.router.llm_client import LLMClient
from app.router.orchestrator import (
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.rag_client import RAGClient, RAGConnectionError
from app.stt.whisper_client import SttClient, SttIndisponivelError

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


def get_stt_client(request: Request) -> SttClient:
    return request.app.state.stt_client


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/messages")
async def send_message(
    payload: ChatMessageRequest,
    local_client: LLMClient = Depends(get_local_client),
    external_client: LLMClient = Depends(get_external_client),
    rag_client: RAGClient = Depends(get_rag_client),
    complexity_strategy: str = Depends(get_complexity_strategy),
    stt_client: SttClient = Depends(get_stt_client),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid4())

    # MVP: quando `payload.audio` vem preenchido, o texto transcrito
    # substitui `payload.message` como mensagem efetiva enviada ao
    # orchestrator (o widget do chat usa áudio como alternativa ao campo de
    # texto — push-to-talk — não como complemento dele). Se a transcrição vier
    # vazia (ex.: áudio sem fala reconhecível), cai de volta para
    # `payload.message`, se houver.
    effective_message = payload.message
    transcribed_message: str | None = None
    if payload.audio:
        try:
            audio_bytes = base64.b64decode(payload.audio, validate=True)
        except binascii.Error as exc:
            raise HTTPException(
                status_code=400, detail="Campo 'audio' não é base64 válido."
            ) from exc

        try:
            transcribed = await stt_client.transcribe(audio_bytes)
        except SttIndisponivelError as exc:
            logger.error(
                "stt_indisponivel",
                extra={"router": {"event": "stt_indisponivel", "erro": str(exc)}},
            )
            raise HTTPException(
                status_code=503, detail="Serviço de transcrição de áudio indisponível."
            ) from exc

        if transcribed:
            effective_message = transcribed
            transcribed_message = transcribed

    if not effective_message:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível entender o áudio. Tente novamente ou digite sua mensagem.",
        )

    recent_messages = list(_conversation_history.get(conversation_id, []))

    async def event_stream():
        yield _sse("conversation", {"conversation_id": conversation_id})
        if transcribed_message is not None:
            yield _sse("transcription", {"transcribed_message": transcribed_message})

        try:
            async for event in handle_message(
                message=effective_message,
                recent_messages=recent_messages,
                local_client=local_client,
                external_client=external_client,
                rag_client=rag_client,
                complexity_strategy=complexity_strategy,
            ):
                if isinstance(event, StatusEvent):
                    yield _sse("status", {"status": event.status})
                elif isinstance(event, TokenEvent):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, RouterDecision):
                    history = _conversation_history.setdefault(conversation_id, [])
                    history.append(effective_message)
                    del history[:-_MAX_HISTORY_MESSAGES]
                    done_data = ChatDoneEventData(
                        domain=event.domain,
                        backend_used=event.backend_escolhido,
                        escalation_reason=event.motivo_escalonamento,
                        model_name=event.modelo_usado,
                        prompt_tokens=event.tokens_entrada,
                        completion_tokens=event.tokens_saida,
                        latency_ms=event.latencia_ms,
                        ttft_ms=event.ttft_ms,
                        tps=event.tps,
                        confidence=event.confidence,
                        complexity=event.complexity,
                        estimated_cost_usd=event.custo_estimado_usd,
                        rag_retrieval_ms=event.rag_retrieval_ms,
                        rag_chunks_count=event.rag_chunks_count,
                        rag_avg_score=event.rag_avg_score,
                    )
                    yield _sse("done", done_data.model_dump())
        except (
            LocalBackendIndisponivelError,
            ExternalBackendIndisponivelError,
            RAGConnectionError,
        ) as exc:
            logger.error(
                "chat_dependencia_indisponivel",
                extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
            )
            yield _sse(
                "error", {"detail": "Serviço temporariamente indisponível, tente novamente."}
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        # MVP: headers mínimos anti-buffering — sem eles, um proxy reverso
        # (ex. nginx) pode segurar o stream até fechar em vez de repassar
        # cada chunk incrementalmente (ver docs/ARCHITECTURE.md §5).
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
