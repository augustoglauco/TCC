"""Endpoint HTTP do chat (R2, R3, R5) — encaminha para o orchestrator do roteador."""

import base64
import binascii
import json
import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.mcp_client.google_calendar import CalendarClient
from app.models.chat import ChatDoneEventData, ChatMessageRequest
from app.models.runtime_settings import DEFAULT_INTENT_ROUTER_PROVIDER, DEFAULT_TONE_MONITOR_PROVIDER
from app.ocr.image_processor import (
    ImageFormatError,
    OcrIndisponivelError,
    detect_image_format,
    extract_text_from_base64,
)
from app.rag.clip_embedder import ClipEmbedder
from app.rag.image_identification import identify_product_by_image
from app.rag.image_search import ClipImageStore
from app.router.llm_client import LLMClient
from app.router.orchestrator import (
    EscalonamentoEvent,
    ExternalBackendIndisponivelError,
    LocalBackendIndisponivelError,
    RouterDecision,
    StatusEvent,
    TokenEvent,
    handle_message,
)
from app.router.rag_client import RAGClient, RAGConnectionError
from app.router.scheduling import SchedulingConfig
from app.router.tone_monitor import criar_escalonamento
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


def get_intent_router_provider(request: Request) -> str:
    return getattr(request.app.state, "intent_router_provider", DEFAULT_INTENT_ROUTER_PROVIDER)


def get_tone_monitor_enabled(request: Request) -> bool:
    return getattr(request.app.state, "tone_monitor_enabled", True)


def get_tone_monitor_provider(request: Request) -> str:
    return getattr(request.app.state, "tone_monitor_provider", DEFAULT_TONE_MONITOR_PROVIDER)


def get_stt_client(request: Request) -> SttClient:
    return request.app.state.stt_client


def get_clip_store(request: Request) -> ClipImageStore:
    return request.app.state.clip_image_store


def get_clip_embedder(request: Request) -> ClipEmbedder:
    return request.app.state.clip_embedder


def get_calendar_client(request: Request) -> CalendarClient:
    return request.app.state.calendar_client


def get_scheduling_config(request: Request) -> SchedulingConfig:
    return request.app.state.scheduling_config


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/messages")
async def send_message(
    payload: ChatMessageRequest,
    request: Request,
    local_client: LLMClient = Depends(get_local_client),
    external_client: LLMClient = Depends(get_external_client),
    rag_client: RAGClient = Depends(get_rag_client),
    complexity_strategy: str = Depends(get_complexity_strategy),
    stt_client: SttClient = Depends(get_stt_client),
    clip_store: ClipImageStore = Depends(get_clip_store),
    clip_embedder: ClipEmbedder = Depends(get_clip_embedder),
    calendar_client: CalendarClient = Depends(get_calendar_client),
    scheduling_config: SchedulingConfig = Depends(get_scheduling_config),
    intent_router_provider: str = Depends(get_intent_router_provider),
    tone_monitor_enabled: bool = Depends(get_tone_monitor_enabled),
    tone_monitor_provider: str = Depends(get_tone_monitor_provider),
    session: AsyncSession = Depends(get_db_session),
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

    # Fluxo de imagem (ver docs/ARCHITECTURE.md §4). O PADRÃO é identificação
    # de produto (mais abaixo, no event_stream); o OCR só roda quando o
    # sistema solicitou um comprovante/documento (`image_intent="documento"`).
    is_identificacao_imagem = bool(payload.image) and payload.image_intent != "documento"

    if payload.image and payload.image_intent == "documento":
        # MVP: OCR extrai o texto da imagem e o concatena à mensagem efetiva
        # (pode combinar com texto digitado). Se o OCR não extrair nada, a
        # imagem é ignorada silenciosamente. Se o Tesseract não estiver
        # disponível mas já houver `effective_message`, degrada graciosamente
        # em vez de derrubar a requisição — mesmo padrão do STT.
        try:
            ocr_text = extract_text_from_base64(payload.image)
            if ocr_text:
                effective_message = (
                    f"{effective_message}\n\n[Texto extraído da imagem]:\n{ocr_text}"
                    if effective_message
                    else f"[Texto extraído da imagem]:\n{ocr_text}"
                )
        except ImageFormatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except OcrIndisponivelError as exc:
            logger.error(
                "ocr_indisponivel",
                extra={"router": {"event": "ocr_indisponivel", "erro": str(exc)}},
            )
            if not effective_message:
                # Sem texto de fallback: sem OCR não há mensagem efetiva.
                raise HTTPException(status_code=503, detail="Serviço de OCR indisponível.") from exc
            # Já há texto digitado: ignora a imagem e continua com o texto.

    # A identificação de produto não exige texto (a imagem é a "mensagem");
    # só exigimos `effective_message` quando NÃO é o fluxo de identificação.
    if not effective_message and not is_identificacao_imagem:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível entender o áudio. Tente novamente ou digite sua mensagem.",
        )

    # Decodifica a imagem para o fluxo de identificação (o base64 do OCR é
    # decodificado dentro de `extract_text_from_base64`; aqui precisamos dos
    # bytes crus para o motor de identificação).
    identificacao_image_bytes: bytes | None = None
    if is_identificacao_imagem:
        try:
            identificacao_image_bytes = base64.b64decode(payload.image, validate=True)
        except binascii.Error as exc:
            raise HTTPException(
                status_code=400, detail="Campo 'image' não é base64 válido."
            ) from exc
        # Valida o formato ANTES do CLIP (mesma barreira de `_validate_image`
        # nos endpoints de imagem). Sem isso, bytes inválidos chegariam ao
        # `PIL.Image.open` dentro do embedder CLIP e estourariam
        # `UnidentifiedImageError` sem tratamento — como o fluxo de
        # identificação roda dentro do stream SSE, o erro travava a resposta
        # silenciosamente (200 OK com corpo vazio, sem nenhum evento). Ver bug
        # relatado 2026-09-20.
        if detect_image_format(identificacao_image_bytes) is None:
            raise HTTPException(
                status_code=400,
                detail="Formato de imagem não suportado. Use PNG, JPG ou WEBP.",
            )

    recent_messages = list(_conversation_history.get(conversation_id, []))

    async def event_stream():
        yield _sse("conversation", {"conversation_id": conversation_id})
        if transcribed_message is not None:
            yield _sse("transcription", {"transcribed_message": transcribed_message})

        # Fluxo padrão de imagem: identificação de produto (ver
        # docs/ARCHITECTURE.md §4). Não passa pelo orchestrator/LLM de texto —
        # produz a própria resposta (detalhes do produto ou "não
        # identificado") e a emite como token + done.
        if is_identificacao_imagem:
            try:
                resultado = await identify_product_by_image(
                    identificacao_image_bytes,
                    clip_store=clip_store,
                    clip_embedder=clip_embedder,
                    vision_client=external_client,
                    rag_client=rag_client,
                    internal_confidence=request.app.state.image_internal_confidence,
                    external_confidence=request.app.state.image_external_confidence,
                    recent_messages=recent_messages,
                )
            except RAGConnectionError as exc:
                logger.error(
                    "chat_dependencia_indisponivel",
                    extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
                )
                yield _sse(
                    "error", {"detail": "Serviço temporariamente indisponível, tente novamente."}
                )
                return

            if resultado.status == "nao_identificado":
                texto = resultado.mensagem or "Não identifiquei o produto."
            else:
                cabecalho = f"Identifiquei: {resultado.produto}."
                texto = f"{cabecalho}\n\n{resultado.detalhes}" if resultado.detalhes else cabecalho
            yield _sse("token", {"text": texto})
            yield _sse(
                "identification",
                resultado.model_dump(exclude_none=True),
            )
            done_data = ChatDoneEventData(
                domain="vendas",
                backend_used="identificacao_imagem",
                escalation_reason="nenhum",
            )
            yield _sse("done", done_data.model_dump())
            return

        try:
            async for event in handle_message(
                message=effective_message,
                recent_messages=recent_messages,
                local_client=local_client,
                external_client=external_client,
                rag_client=rag_client,
                complexity_strategy=complexity_strategy,
                conversation_id=conversation_id,
                calendar_client=calendar_client,
                scheduling_config=scheduling_config,
                intent_router_provider=intent_router_provider,
                tone_monitor_enabled=tone_monitor_enabled,
                tone_monitor_provider=tone_monitor_provider,
            ):
                if isinstance(event, StatusEvent):
                    yield _sse("status", {"status": event.status})
                elif isinstance(event, TokenEvent):
                    yield _sse("token", {"text": event.text})
                elif isinstance(event, EscalonamentoEvent):
                    yield _sse(
                        "escalonamento", {"motivo": event.motivo, "confianca": event.confianca}
                    )
                    logger.info(
                        "tom_escalonado",
                        extra={
                            "router": {
                                "event": "tom_escalonado",
                                "conversation_id": conversation_id,
                                "motivo": event.motivo,
                                "confianca": event.confianca,
                                "provider_efetivo": event.provider_efetivo,
                            }
                        },
                    )
                    await criar_escalonamento(
                        session,
                        conversation_id=conversation_id,
                        mensagem=effective_message,
                        motivo=event.motivo,
                        confianca=event.confianca,
                        provider_efetivo=event.provider_efetivo,
                    )
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
                        rag_chunks=event.rag_chunks,
                        router_provider=event.router_provider,
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
