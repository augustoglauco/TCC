"""Endpoint administrativo de listagem dos casos escalonados pelo Monitor
de Tom (R8, Fase 4B) — ver
docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §6.2. Sem UI
dedicada nesta entrega, só a API, para inspeção manual/demonstração.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.models import TomEscalonamento
from app.models.tom_escalonamentos import EscalonamentoResponse
from app.router.tone_monitor import listar_escalonamentos

router = APIRouter(prefix="/api/admin/tom", tags=["tom-escalonamentos"])


def _to_response(registro: TomEscalonamento) -> EscalonamentoResponse:
    return EscalonamentoResponse(
        id=registro.id,
        conversation_id=registro.conversation_id,
        mensagem=registro.mensagem,
        motivo=registro.motivo,
        confianca=registro.confianca,
        provider_efetivo=registro.provider_efetivo,
        criado_em=registro.criado_em,
    )


@router.get("/escalonamentos", response_model=list[EscalonamentoResponse])
async def get_escalonamentos(
    session: AsyncSession = Depends(get_db_session),
) -> list[EscalonamentoResponse]:
    # MVP: LIMIT 100 fixo, sem paginação — mesma simplicidade de outras
    # listagens administrativas do projeto.
    registros = await listar_escalonamentos(session)
    return [_to_response(registro) for registro in registros]
