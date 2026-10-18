"""Endpoint HTTP do chat (R2, R3, R5) — encaminha para o orchestrator do roteador."""

import base64
import binascii
import json
import logging
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.api.auth import verificar_admin_por_token
from app.background_tasks import spawn_background_task
from app.db.models import Conversa
from app.logging_config import conversation_id_ctx
from app.mcp_client.google_calendar import CalendarClient
from app.memory.resumo import atualizar_resumo, precisa_resumir
from app.memory.store import (
    ContextoConversa,
    carregar_contexto,
    contar_mensagens,
    gravar_aviso_assistente,
    gravar_mensagem_cliente,
    gravar_metricas,
    limpar_conversa,
    listar_mensagens,
    obter_contexto_conversa_anterior,
    registrar_email,
    registrar_troca,
)
from app.models.chat import (
    ChatDoneEventData,
    ChatMessageRequest,
    ConversaCloseRequest,
    ConversaCloseResponse,
    ConversaHistoricoOut,
    ConversaMensagemOut,
)
from app.models.runtime_settings import (
    DEFAULT_INTENT_ROUTER_PROVIDER,
    DEFAULT_TONE_MONITOR_PROVIDER,
)
from app.ocr.image_processor import (
    MAX_IMAGE_BYTES,
    ImageFormatError,
    OcrIndisponivelError,
    detect_image_format,
    extract_text_from_base64,
    imagem_excede_tamanho_maximo,
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
from app.router.sales_catalog import (
    SalesCatalogClient,
    buscar_reserva_ativa,
    detectar_intencao_comprovante,
    texto_parece_conteudo_de_comprovante,
)
from app.router.scheduling import SchedulingConfig
from app.router.tone_monitor import criar_escalonamento
from app.services.atendimento_service import escalar_para_humano
from app.services.chat_closure_service import fechar_conversa
from app.stt.whisper_client import SttClient, SttIndisponivelError
from app.user_profile.classificacao import (
    RESPOSTA_SO_EMAIL,
    Classificacao,
    atualizar_perfil,
    carregar_contexto_cliente,
    e_mensagem_so_de_email,
    extrair_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _carregar_contexto_seguro(app_state, conversation_id: str) -> ContextoConversa:
    """Histórico recente e resumo da conversa, lidos do Postgres (R9, Fase 6).
    Falha do banco (ou `app.state` sem `db_sessionmaker`) vira log e um
    contexto vazio: a resposta sai sem memória, mas sai."""
    try:
        async with app_state.db_sessionmaker() as session:
            return await carregar_contexto(session, conversation_id)
    except Exception as exc:
        _logar_memoria_indisponivel("carregar", exc)
        return ContextoConversa()


async def _registrar_troca_segura(
    app_state,
    conversation_id: str,
    mensagem: str,
    resposta: str,
    dominio: str | None,
    local_client: LLMClient,
    done_data: ChatDoneEventData,
) -> Classificacao | None:
    """Grava a troca antes do `done`: a próxima mensagem sempre encontra esta
    no histórico. Mesma proteção de `_carregar_contexto_seguro`. Na mesma
    sessão recalcula o perfil do visitante (R10), preenche-o em `done_data`
    e guarda as métricas do `done` na resposta (o painel ⚙️ reaparece no
    histórico). A cada `INTERVALO_RESUMO` mensagens novas, dispara o resumo
    em segundo plano, sem esperar por ele."""
    try:
        async with app_state.db_sessionmaker() as session:
            conversa, assistente = await registrar_troca(
                session, conversation_id, mensagem, resposta, dominio
            )
            total = await contar_mensagens(session, conversation_id)
            resumir = precisa_resumir(total, conversa.mensagens_resumidas)
            classificacao = await atualizar_perfil(session, conversation_id, mensagem)
            if classificacao is not None:
                done_data.perfil_usuario = classificacao.perfil
                done_data.perfil_motivo = classificacao.motivo
            await gravar_metricas(session, assistente, done_data.model_dump(mode="json"))
    except Exception as exc:
        _logar_memoria_indisponivel("registrar", exc)
        return None
    if resumir:
        spawn_background_task(
            atualizar_resumo(app_state.db_sessionmaker, conversation_id, local_client)
        )
    if classificacao is not None:
        # Só perfil e motivo: o e-mail do visitante nunca vai para o log.
        logger.info(
            "perfil_classificado",
            extra={
                "router": {
                    "event": "perfil_classificado",
                    "perfil": classificacao.perfil,
                    "motivo": classificacao.motivo,
                }
            },
        )
    return classificacao


async def _registrar_email_seguro(app_state, conversation_id: str, email: str) -> None:
    """Guarda o e-mail na chegada da mensagem (R10). Mesma proteção de
    `_carregar_contexto_seguro`; o e-mail nunca vai para o log."""
    try:
        async with app_state.db_sessionmaker() as session:
            await registrar_email(session, conversation_id, email)
    except Exception as exc:
        _logar_memoria_indisponivel("registrar_email", exc)


async def _carregar_dados_cliente_seguro(
    app_state, email: str | None, apenas_tipo_cliente: bool = False
) -> str | None:
    """Carrega dados cadastrais e histórico de compras/pedidos do cliente se
    houver e-mail associado. Falha vira log e segue sem quebrar a resposta.
    Se apenas_tipo_cliente=True, carrega somente a classificação de relacionamento
    sem expor compras nem dados pessoais sensíveis."""
    if not email:
        return None
    try:
        async with app_state.db_sessionmaker() as session:
            return await carregar_contexto_cliente(
                session, email, apenas_tipo_cliente=apenas_tipo_cliente
            )
    except Exception as exc:
        logger.warning(
            "contexto_cliente_indisponivel",
            extra={
                "router": {
                    "event": "contexto_cliente_indisponivel",
                    "tipo": type(exc).__name__,
                    "erro": str(exc),
                }
            },
        )
        return None


async def _verificar_modo_admin_seguro(app_state, auth_token: str | None) -> bool:
    """Confirma, via `verificar_admin_por_token`, se `auth_token` pertence a
    uma sessão admin de verdade — liga o modo admin do RAG (decisão de
    2026-09-30, docs/ARCHITECTURE.md §6). Ao contrário das outras funções
    `_..._seguro` desta lista (que falham *abertas* para "sem memória" —
    conveniência, não segurança), esta falha *fechada*: qualquer erro (banco
    fora do ar, token ausente) resulta em `False`, nunca em liberar RAG
    completo por acidente."""
    if not auth_token:
        return False
    try:
        async with app_state.db_sessionmaker() as session:
            return await verificar_admin_por_token(session, auth_token)
    except Exception as exc:
        _logar_memoria_indisponivel("verificar_admin", exc)
        return False


async def _carregar_contexto_anterior_seguro(
    app_state, email: str, conversation_id: str
) -> str | None:
    """Carrega o resumo ou histórico condensado da conversa anterior mais recente
    do usuário autenticado (R9/R10). Falha vira log e segue sem quebrar a resposta."""
    try:
        async with app_state.db_sessionmaker() as session:
            return await obter_contexto_conversa_anterior(
                session, email=email, conversa_atual_id=conversation_id
            )
    except Exception as exc:
        _logar_memoria_indisponivel("carregar_contexto_anterior", exc)
        return None


async def _carregar_conversa_db_segura(app_state, conversation_id: str) -> Conversa | None:
    try:
        session_factory = getattr(app_state, "db_sessionmaker", None)
        if not session_factory:
            return None
        async with session_factory() as session:
            return await session.get(Conversa, conversation_id)
    except Exception as exc:
        logger.warning("Falha ao carregar status da conversa %s: %s", conversation_id, exc)
        return None


async def _gravar_mensagem_cliente_segura(app_state, conversation_id: str, texto: str) -> None:
    try:
        session_factory = getattr(app_state, "db_sessionmaker", None)
        if not session_factory:
            return
        async with session_factory() as session:
            await gravar_mensagem_cliente(session, conversation_id, texto)
    except Exception as exc:
        logger.warning("Falha ao gravar mensagem de cliente em atendimento humano: %s", exc)


async def _gravar_aviso_humano_seguro(app_state, conversation_id: str, texto: str) -> None:
    try:
        session_factory = getattr(app_state, "db_sessionmaker", None)
        if not session_factory:
            return
        async with session_factory() as session:
            await gravar_aviso_assistente(session, conversation_id, texto)
    except Exception as exc:
        logger.warning("Falha ao gravar aviso de atendimento humano: %s", exc)


async def _escalar_conversa_em_background(
    session_factory, conversation_id: str, motivo: str, prioridade: int
) -> None:
    try:
        if not session_factory:
            return
        async with session_factory() as session:
            await escalar_para_humano(
                session, conversation_id, motivo=motivo, prioridade=prioridade
            )
    except Exception as exc:
        logger.warning("Falha ao escalar conversa %s em background: %s", conversation_id, exc)


def _logar_memoria_indisponivel(operacao: str, exc: Exception) -> None:
    logger.warning(
        "memoria_indisponivel",
        extra={
            "router": {
                "event": "memoria_indisponivel",
                "operacao": operacao,
                "tipo": type(exc).__name__,
                "erro": str(exc),
            }
        },
    )


def get_local_client(request: Request) -> LLMClient:
    return request.app.state.local_client


def get_external_client(request: Request) -> LLMClient:
    return request.app.state.external_client


def get_rag_client(request: Request) -> RAGClient:
    return request.app.state.rag_client


def get_rag_client_admin(request: Request) -> RAGClient:
    return request.app.state.rag_client_admin


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


def get_sales_catalog_client(request: Request) -> SalesCatalogClient:
    return request.app.state.sales_catalog_client


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _persistir_escalonamento_em_background(
    app_state,
    *,
    conversation_id: str,
    mensagem: str,
    motivo: str | None,
    confianca: float,
    provider_efetivo: str,
) -> None:
    """Roda via `asyncio.create_task` — nunca aguardada pelo stream SSE que a
    disparou, pra não travar a entrega de `token`s bem na mensagem em que o
    cliente já está insatisfeito (achado no code-review, 2026-09-24). Abre
    sua PRÓPRIA sessão (não reaproveita a do request) porque `AsyncSession`
    não é segura para uso concorrente, e a sessão do request pode já ter
    sido encerrada pelo FastAPI antes desta task terminar, já que ela sobra
    rodando depois do generator do stream ser exaurido.

    Recebe `app_state` (não `db_sessionmaker` já resolvido) e só acessa
    `.db_sessionmaker` DENTRO do try/except — achado no code-review
    (2026-09-24, dois agentes independentes): antes, `request.app.state.
    db_sessionmaker` era lido no ponto de chamada, numa expressão síncrona
    fora deste try/except, ao montar os argumentos de `asyncio.create_task`
    — um `AttributeError` ali (ex.: app.state sem esse atributo, cenário só
    de teste/config incompleta) propagaria cru e derrubaria o stream SSE
    logo após o evento `escalonamento`, exatamente o bug que este try/except
    existe para evitar.
    """
    try:
        async with app_state.db_sessionmaker() as session:
            await criar_escalonamento(
                session,
                conversation_id=conversation_id,
                mensagem=mensagem,
                motivo=motivo,
                confianca=confianca,
                provider_efetivo=provider_efetivo,
            )
    except Exception as exc:
        logger.warning(
            "tom_escalonamento_persistencia_falhou",
            extra={
                "router": {
                    "event": "tom_escalonamento_persistencia_falhou",
                    "conversation_id": conversation_id,
                    "erro": str(exc),
                }
            },
        )


@router.get("/conversations/{conversation_id}", response_model=ConversaHistoricoOut)
async def obter_conversa(conversation_id: str, request: Request) -> ConversaHistoricoOut:
    """Histórico gravado da conversa (R9, Fase 6), mais antigo primeiro — o
    widget chama ao abrir, para reexibir a conversa no mesmo navegador.

    # MVP: quem tiver o `conversation_id` (UUID aleatório guardado no
    # navegador) lê a conversa; sem login nem outra verificação.
    """
    try:
        async with request.app.state.db_sessionmaker() as session:
            conversa = await session.get(Conversa, conversation_id)
            if conversa is None:
                raise HTTPException(status_code=404, detail="Conversa não encontrada.")
            # Achado de 2026-10-08: sem `limite=None`, caía no default de 50
            # (`app.memory.store.listar_mensagens`), cortando silenciosamente
            # o histórico/telemetria de conversas com mais de 25 trocas.
            mensagens = await listar_mensagens(session, conversation_id, limite=None)
    except HTTPException:
        raise
    except Exception as exc:
        _logar_memoria_indisponivel("obter_conversa", exc)
        raise HTTPException(status_code=503, detail="Histórico indisponível no momento.") from exc
    return ConversaHistoricoOut(
        conversation_id=conversation_id,
        status=conversa.status,
        encerrada_em=conversa.encerrada_em,
        motivo_encerramento=conversa.motivo_encerramento,
        resumo=conversa.resumo,
        mensagens=[
            ConversaMensagemOut(
                papel=m.papel,
                texto=m.texto,
                dominio=m.dominio,
                criada_em=m.criada_em,
                atendente_nome=m.atendente_nome,
                metricas=m.metricas,
            )
            for m in mensagens
        ],
    )


@router.post("/conversations/{conversation_id}/close", response_model=ConversaCloseResponse)
async def fechar_conversa_endpoint(
    conversation_id: str,
    request: Request,
    payload: ConversaCloseRequest | None = None,
) -> ConversaCloseResponse:
    """Encerra a conversa manualmente pelo visitante ou admin (R9/Metricas)."""
    motivo = payload.motivo if payload else "manual_usuario"
    try:
        session_factory = getattr(request.app.state, "db_sessionmaker", None)
        if not session_factory:
            raise HTTPException(status_code=503, detail="Banco de dados não configurado.")
        async with session_factory() as session:
            conversa = await fechar_conversa(session, conversation_id, motivo=motivo)
            if conversa is None:
                raise HTTPException(status_code=404, detail="Conversa não encontrada.")
            return ConversaCloseResponse(
                conversation_id=conversa.id,
                status=conversa.status,
                encerrada_em=conversa.encerrada_em,
                motivo_encerramento=conversa.motivo_encerramento,
            )
    except HTTPException:
        raise
    except Exception as exc:
        _logar_memoria_indisponivel("fechar_conversa", exc)
        raise HTTPException(
            status_code=503, detail="Não foi possível encerrar a conversa."
        ) from exc


@router.delete("/conversations/{conversation_id}", status_code=204)
async def deletar_conversa(conversation_id: str, request: Request) -> None:
    """Deleta todas as mensagens e reseta os campos de memória/resumo no Postgres."""
    try:
        async with request.app.state.db_sessionmaker() as session:
            removido = await limpar_conversa(session, conversation_id)
            if not removido:
                raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    except HTTPException:
        raise
    except Exception as exc:
        _logar_memoria_indisponivel("deletar_conversa", exc)
        raise HTTPException(status_code=503, detail="Não foi possível limpar a conversa.") from exc


@router.post("/conversations/{conversation_id}/transbordo")
async def solicitar_transbordo(
    conversation_id: str,
    request: Request,
) -> dict[str, Any]:
    """Solicita transbordo para atendimento humano sob demanda pelo cliente."""
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")
    async with session_factory() as session:
        conv = await escalar_para_humano(
            session,
            conversation_id=conversation_id,
            motivo="solicitacao_direta",
            prioridade=3,
        )
        return {
            "conversation_id": conv.id,
            "status": conv.status,
            "motivo_escalonamento": conv.motivo_escalonamento,
            "prioridade": conv.prioridade,
            "escalado_em": conv.escalado_em.isoformat() if conv.escalado_em else None,
        }


@dataclass
class _AudioPreprocessado:
    effective_message: str | None
    transcribed_message: str | None


@dataclass
class _ImagemPreprocessada:
    effective_message: str | None
    is_identificacao_imagem: bool
    imagem_e_documento: bool
    identificacao_image_bytes: bytes | None


async def _preprocessar_audio(
    payload_message: str | None,
    audio_b64: str | None,
    stt_client: SttClient,
) -> _AudioPreprocessado:
    """Decodifica e transcreve áudio; retorna mensagem efetiva e transcrição."""
    if not audio_b64:
        return _AudioPreprocessado(effective_message=payload_message, transcribed_message=None)
    try:
        audio_bytes = base64.b64decode(audio_b64, validate=True)
    except binascii.Error as exc:
        raise HTTPException(status_code=400, detail="Campo 'audio' não é base64 válido.") from exc
    try:
        transcribed = await stt_client.transcribe(audio_bytes)
    except SttIndisponivelError as exc:
        logger.error(
            "stt_indisponivel", extra={"router": {"event": "stt_indisponivel", "erro": str(exc)}}
        )
        raise HTTPException(
            status_code=503, detail="Serviço de transcrição de áudio indisponível."
        ) from exc
    if transcribed:
        return _AudioPreprocessado(effective_message=transcribed, transcribed_message=transcribed)
    return _AudioPreprocessado(effective_message=payload_message, transcribed_message=None)


def _processar_ocr_documento(
    image_b64: str,
    effective_message: str | None,
    forcado_so_por_reserva_pendente: bool,
) -> tuple[str | None, bool]:
    """Roda OCR e decide se a imagem continua sendo documento.
    Devolve (effective_message atualizada, imagem_e_documento).
    Levanta HTTPException em erros de formato ou OCR sem mensagem de fallback."""
    try:
        ocr_text = extract_text_from_base64(image_b64)
        if forcado_so_por_reserva_pendente and not texto_parece_conteudo_de_comprovante(
            ocr_text or ""
        ):
            return effective_message, False
        if ocr_text:
            effective_message = (
                f"{effective_message}\n\n[Texto extraído da imagem]:\n{ocr_text}"
                if effective_message
                else f"[Texto extraído da imagem]:\n{ocr_text}"
            )
        return effective_message, True
    except ImageFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OcrIndisponivelError as exc:
        logger.error(
            "ocr_indisponivel", extra={"router": {"event": "ocr_indisponivel", "erro": str(exc)}}
        )
        if not effective_message:
            raise HTTPException(status_code=503, detail="Serviço de OCR indisponível.") from exc
        return effective_message, True


async def _preprocessar_imagem(
    image_b64: str | None,
    image_intent: str | None,
    effective_message: str | None,
    conversation_id: str,
    user_email: str | None,
    app_state,
) -> _ImagemPreprocessada:
    """Detecta intenção (comprovante vs. identificação), roda OCR se necessário,
    valida bytes para CLIP. Retorna flags e mensagem efetiva atualizada."""
    if not image_b64:
        return _ImagemPreprocessada(
            effective_message=effective_message,
            is_identificacao_imagem=False,
            imagem_e_documento=False,
            identificacao_image_bytes=None,
        )

    tem_reserva_pendente = False
    session_factory = getattr(app_state, "db_sessionmaker", None)
    if session_factory:
        try:
            async with session_factory() as session:
                reserva = await buscar_reserva_ativa(
                    session, conversation_id=conversation_id, user_email=user_email
                )
            tem_reserva_pendente = reserva is not None
        except Exception as exc:
            _logar_memoria_indisponivel("verificar_reserva_pendente", exc)

    comprovante_por_legenda_ou_intent = (
        image_intent == "documento" or detectar_intencao_comprovante(effective_message or "")
    )
    imagem_e_documento = comprovante_por_legenda_ou_intent or tem_reserva_pendente
    is_identificacao_imagem = not imagem_e_documento
    forcado_so_por_reserva_pendente = tem_reserva_pendente and not comprovante_por_legenda_ou_intent

    if imagem_e_documento:
        effective_message, imagem_e_documento = _processar_ocr_documento(
            image_b64, effective_message, forcado_so_por_reserva_pendente
        )
        is_identificacao_imagem = not imagem_e_documento

    identificacao_image_bytes: bytes | None = None
    if is_identificacao_imagem:
        try:
            identificacao_image_bytes = base64.b64decode(image_b64, validate=True)
        except binascii.Error as exc:
            raise HTTPException(
                status_code=400, detail="Campo 'image' não é base64 válido."
            ) from exc
        if detect_image_format(identificacao_image_bytes) is None:
            raise HTTPException(
                status_code=400, detail="Formato de imagem não suportado. Use PNG, JPG ou WEBP."
            )
        if imagem_excede_tamanho_maximo(identificacao_image_bytes):
            raise HTTPException(
                status_code=413,
                detail=(
                    "Imagem excede o tamanho máximo permitido "
                    f"({MAX_IMAGE_BYTES // (1024 * 1024)}MB)."
                ),
            )

    return _ImagemPreprocessada(
        effective_message=effective_message,
        is_identificacao_imagem=is_identificacao_imagem,
        imagem_e_documento=imagem_e_documento,
        identificacao_image_bytes=identificacao_image_bytes,
    )


_RE_PEDE_HUMANO = re.compile(
    r"\b(atendente humano|falar com humano|suporte humano|operador humano"
    r"|atendimento humano|quero humano|chama um humano)\b"
)


async def _verificar_atendimento_humano(
    effective_message: str | None,
    conversation_id: str,
    app_state,
) -> Conversa | None:
    """Retorna a Conversa se estiver (ou acabar de entrar) em atendimento humano.

    Devolve None caso contrário.
    """
    pede_humano = bool(effective_message and _RE_PEDE_HUMANO.search(effective_message.lower()))
    conversa_db = await _carregar_conversa_db_segura(app_state, conversation_id)
    if pede_humano and (
        conversa_db is None
        or conversa_db.status not in ("aguardando_humano", "em_atendimento_humano")
    ):
        session_factory = getattr(app_state, "db_sessionmaker", None)
        if session_factory:
            async with session_factory() as session:
                conversa_db = await escalar_para_humano(
                    session, conversation_id, motivo="solicitacao_direta", prioridade=3
                )
    if conversa_db and conversa_db.status in ("aguardando_humano", "em_atendimento_humano"):
        return conversa_db
    return None


async def _stream_identificacao_imagem(
    *,
    identificacao_image_bytes: bytes | None,
    effective_message: str | None,
    clip_store: ClipImageStore,
    clip_embedder: ClipEmbedder,
    external_client: LLMClient,
    rag_client: RAGClient,
    app_state,
    recent_messages,
    sales_catalog_client: SalesCatalogClient,
    conversation_id: str,
    local_client: LLMClient,
):
    """Gerador SSE para o fluxo de identificação de produto por imagem."""
    try:
        resultado = await identify_product_by_image(
            identificacao_image_bytes,
            clip_store=clip_store,
            clip_embedder=clip_embedder,
            vision_client=external_client,
            rag_client=rag_client,
            internal_confidence=app_state.image_internal_confidence,
            external_confidence=app_state.image_external_confidence,
            recent_messages=recent_messages,
            sales_catalog_client=sales_catalog_client,
        )
    except RAGConnectionError as exc:
        logger.error(
            "chat_dependencia_indisponivel",
            extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
        )
        yield _sse("error", {"detail": "Serviço temporariamente indisponível, tente novamente."})
        return

    if resultado.status == "nao_identificado":
        texto = resultado.mensagem or "Não identifiquei o produto."
    else:
        cabecalho = f"Identifiquei: {resultado.produto}."
        texto = f"{cabecalho}\n\n{resultado.detalhes}" if resultado.detalhes else cabecalho
    yield _sse("token", {"text": texto})
    yield _sse("identification", resultado.model_dump(exclude_none=True))
    has_vision_call = (
        resultado.prompt_tokens is not None
        or resultado.cost_prompt_usd is not None
        or (resultado.fonte and "visao_externa" in resultado.fonte)
    )
    total_tokens = resultado.total_tokens
    if total_tokens is None and (
        resultado.prompt_tokens is not None or resultado.completion_tokens is not None
    ):
        total_tokens = (resultado.prompt_tokens or 0) + (resultado.completion_tokens or 0)
    done_data = ChatDoneEventData(
        domain="vendas",
        backend_used="externo" if has_vision_call else "identificacao_imagem",
        escalation_reason="nenhum",
        model_name=resultado.model_name,
        prompt_tokens=resultado.prompt_tokens,
        completion_tokens=resultado.completion_tokens,
        total_tokens=total_tokens,
        cost_prompt_usd=resultado.cost_prompt_usd,
        cost_completion_usd=resultado.cost_completion_usd,
        estimated_cost_usd=resultado.estimated_cost_usd,
        vision_used=True,
    )
    await _registrar_troca_segura(
        app_state,
        conversation_id,
        f"[imagem enviada] {effective_message}".strip()
        if effective_message
        else "[imagem enviada]",
        texto,
        "vendas",
        local_client,
        done_data,
    )
    yield _sse("done", done_data.model_dump(mode="json"))


def _router_decision_para_done_data(event: RouterDecision) -> ChatDoneEventData:
    return ChatDoneEventData(
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
        cost_prompt_usd=event.cost_prompt_usd,
        cost_completion_usd=event.cost_completion_usd,
        estimated_cost_usd=event.custo_estimado_usd,
        rag_retrieval_ms=event.rag_retrieval_ms,
        rag_chunks_count=event.rag_chunks_count,
        rag_avg_score=event.rag_avg_score,
        rag_chunks=event.rag_chunks,
        router_provider=event.router_provider,
        card=event.card,
    )


def _resolver_complexity_strategy(intent_router_provider: str, complexity_strategy: str) -> str:
    """Mapeia o provider do roteador para a estratégia de complexidade efetiva."""
    if intent_router_provider == "heuristica_llm":
        return "llm"
    if intent_router_provider == "heuristica":
        return "heuristic"
    return complexity_strategy


def _decodificar_comprovante(payload_image: str | None, imagem_e_documento: bool) -> bytes | None:
    """Decodifica o base64 do comprovante; retorna None se ausente ou inválido."""
    if not (payload_image and imagem_e_documento):
        return None
    try:
        return base64.b64decode(payload_image, validate=True)
    except Exception:
        return None


def _despachar_escalonamento(
    event: EscalonamentoEvent,
    app_state,
    conversation_id: str,
    effective_message: str | None,
) -> None:
    """Loga e agenda tarefas de background para um evento de escalonamento."""
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
    spawn_background_task(
        _persistir_escalonamento_em_background(
            app_state,
            conversation_id=conversation_id,
            mensagem=effective_message,
            motivo=event.motivo,
            confianca=event.confianca,
            provider_efetivo=event.provider_efetivo,
        )
    )
    spawn_background_task(
        _escalar_conversa_em_background(
            getattr(app_state, "db_sessionmaker", None),
            conversation_id=conversation_id,
            motivo=event.motivo or "tom_frustrado",
            prioridade=5,
        )
    )


async def _stream_llm(
    *,
    payload_image: str | None,
    effective_message: str | None,
    so_email: bool,
    imagem_e_documento: bool,
    recent_messages,
    local_client: LLMClient,
    external_client: LLMClient,
    rag_client: RAGClient,
    complexity_strategy: str,
    conversation_id: str,
    calendar_client: CalendarClient,
    scheduling_config: SchedulingConfig,
    sales_catalog_client: SalesCatalogClient,
    intent_router_provider: str,
    tone_monitor_enabled: bool,
    tone_monitor_provider: str,
    contexto,
    dados_cliente: str | None,
    contexto_anterior: str | None,
    is_admin: bool,
    email_cliente: str | None,
    usuario_autenticado: bool,
    app_state,
):
    """Gerador SSE para o fluxo principal: resposta fixa de e-mail ou LLM/RAG."""
    if so_email:
        yield _sse("token", {"text": RESPOSTA_SO_EMAIL})
        done_data = ChatDoneEventData(
            domain="atendimento", backend_used="resposta_fixa", escalation_reason="nenhum"
        )
        await _registrar_troca_segura(
            app_state,
            conversation_id,
            effective_message,
            RESPOSTA_SO_EMAIL,
            "atendimento",
            local_client,
            done_data,
        )
        yield _sse("done", done_data.model_dump(mode="json"))
        return

    efetiva_complexity_strategy = _resolver_complexity_strategy(
        intent_router_provider, complexity_strategy
    )
    comprovante_bytes = _decodificar_comprovante(payload_image, imagem_e_documento)

    partes_resposta: list[str] = []
    try:
        async for event in handle_message(
            message=effective_message,
            recent_messages=recent_messages,
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy=efetiva_complexity_strategy,
            conversation_id=conversation_id,
            calendar_client=calendar_client,
            scheduling_config=scheduling_config,
            sales_catalog_client=sales_catalog_client,
            intent_router_provider=intent_router_provider,
            tone_monitor_enabled=tone_monitor_enabled,
            tone_monitor_provider=tone_monitor_provider,
            resumo_conversa=contexto.resumo,
            ultima_troca=contexto.ultima_troca,
            pedir_email_pos_venda=contexto.email is None,
            dados_cliente=dados_cliente,
            contexto_conversa_anterior=contexto_anterior,
            db_sessionmaker=getattr(app_state, "db_sessionmaker", None),
            rag_top_k=getattr(app_state, "rag_top_k", 3),
            rag_score_threshold=getattr(app_state, "rag_score_threshold", 0.35),
            rag_download_threshold=getattr(app_state, "rag_download_confidence_threshold", 0.65),
            is_admin=is_admin,
            user_email=email_cliente,
            usuario_autenticado=usuario_autenticado,
            comprovante_bytes=comprovante_bytes,
            comprovante_filename="comprovante.png" if comprovante_bytes else None,
        ):
            if isinstance(event, StatusEvent):
                yield _sse("status", {"status": event.status})
            elif isinstance(event, TokenEvent):
                partes_resposta.append(event.text)
                yield _sse("token", {"text": event.text})
            elif isinstance(event, EscalonamentoEvent):
                yield _sse("escalonamento", {"motivo": event.motivo, "confianca": event.confianca})
                _despachar_escalonamento(event, app_state, conversation_id, effective_message)
            elif isinstance(event, RouterDecision):
                done_data = _router_decision_para_done_data(event)
                await _registrar_troca_segura(
                    app_state,
                    conversation_id,
                    effective_message,
                    "".join(partes_resposta),
                    event.domain,
                    local_client,
                    done_data,
                )
                yield _sse("done", done_data.model_dump(mode="json"))
    except (
        LocalBackendIndisponivelError,
        ExternalBackendIndisponivelError,
        RAGConnectionError,
    ) as exc:
        logger.error(
            "chat_dependencia_indisponivel",
            extra={"router": {"event": "chat_dependencia_indisponivel", "erro": str(exc)}},
        )
        yield _sse("error", {"detail": "Serviço temporariamente indisponível, tente novamente."})


async def _resolver_email_cliente(
    app_state,
    conversation_id: str,
    user_email_payload: str | None,
    effective_message: str | None,
    contexto,
) -> tuple[bool, str | None]:
    """R10: resolve (usuario_autenticado, email_cliente).
    Autenticado → usa email do payload e persiste se mudou.
    Deslogado → extrai da mensagem ou usa o prévio da conversa.
    Devolve (usuario_autenticado, email_cliente)."""
    usuario_autenticado = bool(user_email_payload and user_email_payload.strip())
    email_autenticado = user_email_payload.strip().lower() if usuario_autenticado else None
    email_na_mensagem = extrair_email(effective_message) if effective_message else None

    if usuario_autenticado and email_autenticado:
        if contexto.email != email_autenticado:
            await _registrar_email_seguro(app_state, conversation_id, email_autenticado)
            contexto.email = email_autenticado
        return True, email_autenticado

    email_cliente = email_na_mensagem or contexto.email
    if email_na_mensagem and contexto.email != email_na_mensagem:
        await _registrar_email_seguro(app_state, conversation_id, email_na_mensagem)
        contexto.email = email_na_mensagem
    return False, email_cliente


@router.post("/messages")
async def send_message(
    payload: ChatMessageRequest,
    request: Request,
    local_client: LLMClient = Depends(get_local_client),
    external_client: LLMClient = Depends(get_external_client),
    rag_client: RAGClient = Depends(get_rag_client),
    rag_client_admin: RAGClient = Depends(get_rag_client_admin),
    complexity_strategy: str = Depends(get_complexity_strategy),
    stt_client: SttClient = Depends(get_stt_client),
    clip_store: ClipImageStore = Depends(get_clip_store),
    clip_embedder: ClipEmbedder = Depends(get_clip_embedder),
    calendar_client: CalendarClient = Depends(get_calendar_client),
    scheduling_config: SchedulingConfig = Depends(get_scheduling_config),
    sales_catalog_client: SalesCatalogClient = Depends(get_sales_catalog_client),
    intent_router_provider: str = Depends(get_intent_router_provider),
    tone_monitor_enabled: bool = Depends(get_tone_monitor_enabled),
    tone_monitor_provider: str = Depends(get_tone_monitor_provider),
) -> StreamingResponse:
    conversation_id = payload.conversation_id or str(uuid4())
    conversation_id_ctx.set(conversation_id)

    audio_prep = await _preprocessar_audio(payload.message, payload.audio, stt_client)
    effective_message = audio_prep.effective_message
    transcribed_message = audio_prep.transcribed_message

    img_prep = await _preprocessar_imagem(
        payload.image,
        payload.image_intent,
        effective_message,
        conversation_id,
        payload.user_email,
        request.app.state,
    )
    effective_message = img_prep.effective_message
    is_identificacao_imagem = img_prep.is_identificacao_imagem
    imagem_e_documento = img_prep.imagem_e_documento
    identificacao_image_bytes = img_prep.identificacao_image_bytes

    if not effective_message and not is_identificacao_imagem:
        raise HTTPException(
            status_code=422,
            detail="Não foi possível entender o áudio. Tente novamente ou digite sua mensagem.",
        )

    conversa_db = await _verificar_atendimento_humano(
        effective_message, conversation_id, request.app.state
    )
    if conversa_db is not None:
        await _gravar_mensagem_cliente_segura(request.app.state, conversation_id, effective_message)

        async def event_stream_humano():
            conversation_id_ctx.set(conversation_id)
            yield _sse("conversation", {"conversation_id": conversation_id})
            yield _sse(
                "status",
                {
                    "status": conversa_db.status,
                    "atendente_id": conversa_db.atendente_id,
                    "atendente_nome": conversa_db.atendente_nome,
                },
            )
            texto_aviso = (
                f"Mensagem recebida por {conversa_db.atendente_nome}."
                if conversa_db.status == "em_atendimento_humano" and conversa_db.atendente_nome
                else "Sua mensagem foi recebida. Um atendente humano responderá em breve."
            )
            await _gravar_aviso_humano_seguro(request.app.state, conversation_id, texto_aviso)
            yield _sse("token", {"text": texto_aviso})
            yield _sse(
                "done",
                {
                    "domain": "atendimento_humano",
                    "backend_used": "humano",
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cost_prompt_usd": 0.0,
                    "cost_completion_usd": 0.0,
                    "estimated_cost_usd": 0.0,
                    "conversa_status": conversa_db.status,
                },
            )

        return StreamingResponse(
            event_stream_humano(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    contexto = await _carregar_contexto_seguro(request.app.state, conversation_id)
    recent_messages = contexto.mensagens_recentes

    # Modo admin do RAG (decisão de 2026-09-30, docs/ARCHITECTURE.md §6):
    # troca o cliente RAG usado no resto desta mensagem por
    # `rag_client_admin` (busca a collection chat ativa + mcp_b2b + admin)
    # só quando `payload.auth_token` prova, no servidor, uma sessão admin de
    # verdade — nunca a partir de `payload.user_email` (livre).
    is_admin = await _verificar_modo_admin_seguro(request.app.state, payload.auth_token)
    if is_admin:
        rag_client = rag_client_admin

    usuario_autenticado, email_cliente = await _resolver_email_cliente(
        request.app.state, conversation_id, payload.user_email, effective_message, contexto
    )

    dados_cliente = await _carregar_dados_cliente_seguro(
        request.app.state,
        email_cliente,
        apenas_tipo_cliente=not usuario_autenticado,
    )

    contexto_anterior: str | None = None
    if usuario_autenticado and email_cliente:
        contexto_anterior = await _carregar_contexto_anterior_seguro(
            request.app.state, email_cliente, conversation_id
        )

    # Mensagem que é só o e-mail: resposta fixa, sem LLM (ver abaixo).
    so_email = (
        not is_identificacao_imagem
        and bool(effective_message)
        and e_mensagem_so_de_email(effective_message)
    )

    async def event_stream():
        conversation_id_ctx.set(conversation_id)
        yield _sse("conversation", {"conversation_id": conversation_id})
        if transcribed_message is not None:
            yield _sse("transcription", {"transcribed_message": transcribed_message})
        if is_identificacao_imagem:
            async for chunk in _stream_identificacao_imagem(
                identificacao_image_bytes=identificacao_image_bytes,
                effective_message=effective_message,
                clip_store=clip_store,
                clip_embedder=clip_embedder,
                external_client=external_client,
                rag_client=rag_client,
                app_state=request.app.state,
                recent_messages=recent_messages,
                sales_catalog_client=sales_catalog_client,
                conversation_id=conversation_id,
                local_client=local_client,
            ):
                yield chunk
            return
        async for chunk in _stream_llm(
            payload_image=payload.image,
            effective_message=effective_message,
            so_email=so_email,
            imagem_e_documento=imagem_e_documento,
            recent_messages=recent_messages,
            local_client=local_client,
            external_client=external_client,
            rag_client=rag_client,
            complexity_strategy=complexity_strategy,
            conversation_id=conversation_id,
            calendar_client=calendar_client,
            scheduling_config=scheduling_config,
            sales_catalog_client=sales_catalog_client,
            intent_router_provider=intent_router_provider,
            tone_monitor_enabled=tone_monitor_enabled,
            tone_monitor_provider=tone_monitor_provider,
            contexto=contexto,
            dados_cliente=dados_cliente,
            contexto_anterior=contexto_anterior,
            is_admin=is_admin,
            email_cliente=email_cliente,
            usuario_autenticado=usuario_autenticado,
            app_state=request.app.state,
        ):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
