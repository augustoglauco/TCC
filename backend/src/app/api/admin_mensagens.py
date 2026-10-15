"""Caixa de entrada de mensagens de agentes autônomos para o administrador
(R13, `docs/ARCHITECTURE.md`, decisão de 2026-10-15)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.db.models import MensagemAgente

router = APIRouter(
    prefix="/api/admin/agentes/mensagens",
    tags=["Admin Mensagens de Agentes"],
    dependencies=[Depends(require_admin)],
)


class MensagemAgenteOut(BaseModel):
    id: uuid.UUID
    agente: str
    tipo: str
    severidade: str
    titulo: str
    corpo: str
    dados: dict[str, Any] | None
    lida: bool
    email_status: str
    criado_em: datetime | None


class MensagensResposta(BaseModel):
    mensagens: list[MensagemAgenteOut]
    nao_lidas: int


async def _nao_lidas(session: AsyncSession) -> int:
    total = await session.scalar(
        select(func.count()).select_from(MensagemAgente).where(MensagemAgente.lida.is_(False))
    )
    return int(total or 0)


@router.get("", response_model=MensagensResposta)
async def listar_mensagens(
    apenas_nao_lidas: bool = Query(False),
    agente: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> MensagensResposta:
    consulta = select(MensagemAgente).order_by(MensagemAgente.criado_em.desc()).limit(limit)
    if apenas_nao_lidas:
        consulta = consulta.where(MensagemAgente.lida.is_(False))
    if agente:
        consulta = consulta.where(MensagemAgente.agente == agente)
    linhas = (await session.scalars(consulta)).all()
    return MensagensResposta(
        mensagens=[MensagemAgenteOut.model_validate(m, from_attributes=True) for m in linhas],
        nao_lidas=await _nao_lidas(session),
    )


@router.post("/lidas", response_model=MensagensResposta)
async def marcar_todas_lidas(
    session: AsyncSession = Depends(get_db_session),
) -> MensagensResposta:
    await session.execute(
        update(MensagemAgente).where(MensagemAgente.lida.is_(False)).values(lida=True)
    )
    await session.commit()
    return await listar_mensagens(session=session)


@router.post("/{mensagem_id}/lida", response_model=MensagemAgenteOut)
async def marcar_lida(
    mensagem_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> MensagemAgenteOut:
    mensagem = await session.get(MensagemAgente, mensagem_id)
    if mensagem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mensagem não encontrada.")
    mensagem.lida = True
    await session.commit()
    return MensagemAgenteOut.model_validate(mensagem, from_attributes=True)
