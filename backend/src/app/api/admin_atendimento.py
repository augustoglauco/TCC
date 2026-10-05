"""Endpoints REST administrativos para a Central de Atendimento Humano e Fila de Transbordo."""

import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.services import atendimento_service

logger = logging.getLogger("assistente.admin_atendimento")

router = APIRouter(
    prefix="/api/admin/atendimento",
    tags=["Admin Atendimento"],
    dependencies=[Depends(require_admin)],
)


class ClaimRequest(BaseModel):
    atendente_id: str = Field(..., min_length=1, description="Identificador do atendente/operador")
    atendente_nome: str = Field(..., min_length=1, description="Nome de exibição do atendente")


class MensagemAtendenteRequest(BaseModel):
    atendente_nome: str = Field(..., min_length=1, description="Nome do atendente")
    texto: str = Field(..., min_length=1, description="Conteúdo da mensagem para o cliente")


class CloseRequest(BaseModel):
    acao: Literal["finalizar", "devolver_ia"] = Field(..., description="Ação: finalizar ou devolver_ia")
    motivo: str | None = Field(default=None, description="Motivo ou resolução do atendimento")


@router.get("/fila")
async def get_fila_espera(
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retorna as conversas em fila de espera (aguardando_humano) ordenadas por prioridade desc e tempo."""
    return await atendimento_service.listar_fila_espera(session)


@router.get("/meus-chats")
async def get_meus_chats(
    atendente_id: str = Query(..., min_length=1, description="ID do atendente"),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retorna os chats sob responsabilidade ativa do atendente autenticado."""
    return await atendimento_service.listar_meus_chats(session, atendente_id)


@router.get("/{conversation_id}")
async def get_detalhes_conversa(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retorna dados completos da conversa, mensagens e contexto do cliente."""
    detalhes = await atendimento_service.obter_detalhes_atendimento(session, conversation_id)
    if not detalhes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversa {conversation_id} não encontrada.",
        )
    return detalhes


@router.post("/{conversation_id}/claim")
async def post_claim_conversa(
    conversation_id: str,
    payload: ClaimRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Tenta assumir o atendimento de uma conversa na fila de espera.
    
    Utiliza lock atômico condicional. Se outro atendente assumir antes, retorna HTTP 409 Conflict.
    """
    sucesso = await atendimento_service.claim_conversa(
        session,
        conversation_id=conversation_id,
        atendente_id=payload.atendente_id,
        atendente_nome=payload.atendente_nome,
    )
    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta conversa já foi assumida por outro atendente ou não está mais aguardando atendimento.",
        )

    return {
        "status": "em_atendimento_humano",
        "conversation_id": conversation_id,
        "atendente_id": payload.atendente_id,
        "atendente_nome": payload.atendente_nome,
    }


@router.post("/{conversation_id}/mensagem")
async def post_mensagem_atendente(
    conversation_id: str,
    payload: MensagemAtendenteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Envia uma mensagem do atendente humano para o cliente e persiste com papel 'atendente'."""
    msg = await atendimento_service.enviar_mensagem_atendente(
        session,
        conversation_id=conversation_id,
        atendente_nome=payload.atendente_nome,
        texto=payload.texto,
    )
    return {
        "id": msg.id,
        "conversa_id": msg.conversa_id,
        "papel": msg.papel,
        "texto": msg.texto,
        "atendente_nome": msg.atendente_nome,
        "criado_em": msg.criada_em.isoformat() if msg.criada_em else None,
    }


@router.post("/{conversation_id}/close")
async def post_close_conversa(
    conversation_id: str,
    payload: CloseRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Encerra a sessão de atendimento ou devolve o controle da conversa para a IA."""
    if payload.acao == "finalizar":
        conv = await atendimento_service.finalizar_atendimento(
            session, conversation_id, motivo=payload.motivo
        )
    elif payload.acao == "devolver_ia":
        conv = await atendimento_service.devolver_para_ia(session, conversation_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ação inválida. Escolha 'finalizar' ou 'devolver_ia'.",
        )

    return {
        "status": conv.status,
        "conversation_id": conversation_id,
    }
