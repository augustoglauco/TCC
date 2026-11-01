"""Confirmação/cancelamento das propostas de ferramenta do Admin no chat."""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.propostas import PropostaInvalidaError, cancelar, confirmar
from app.api.admin_auth import require_admin
from app.api.auth import MOCK_TOKEN_PREFIX
from app.api.rag_dependencies import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/chat/acoes", tags=["admin-chat-acoes"])


def _admin_id(
    authorization: Annotated[str | None, Header()] = None,
    x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
    token_param: Annotated[str | None, Query(alias="token")] = None,
) -> int:
    """Id do admin a partir do token (já validado por `require_admin`)."""
    token = (authorization or "").split()[-1] if authorization else (x_auth_token or token_param)
    try:
        return int((token or "").removeprefix(MOCK_TOKEN_PREFIX))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Token inválido.") from exc


@router.post("/{acao_id}/confirmar", dependencies=[Depends(require_admin)])
async def post_confirmar(
    acao_id: uuid.UUID,
    admin_id: int = Depends(_admin_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        acao = await confirmar(session, acao_id, admin_id=admin_id)
    except PropostaInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Falha ao executar a ação %s do chat Admin", acao_id)
        raise HTTPException(
            status_code=409, detail="Não foi possível executar a ação; nada foi gravado."
        ) from exc
    return {"status": acao.status, "depois": acao.depois}


@router.post("/{acao_id}/cancelar", dependencies=[Depends(require_admin)])
async def post_cancelar(
    acao_id: uuid.UUID,
    admin_id: int = Depends(_admin_id),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        acao = await cancelar(session, acao_id, admin_id=admin_id)
    except PropostaInvalidaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": acao.status}
