"""Endpoint administrativo de listagem dos casos escalonados pelo Monitor
de Tom (R8, Fase 4B) — ver
docs/superpowers/specs/2026-09-23-monitor-de-tom-design.md §6.2. Sem UI
dedicada nesta entrega, só a API, para inspeção manual/demonstração.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.models.tom_escalonamentos import EscalonamentoResponse
from app.router.tone_monitor import listar_escalonamentos

router = APIRouter(prefix="/api/admin/tom", tags=["tom-escalonamentos"])


@router.get("/escalonamentos", response_model=list[EscalonamentoResponse])
async def get_escalonamentos(
    session: AsyncSession = Depends(get_db_session),
) -> list[EscalonamentoResponse]:
    # MVP: LIMIT 100 fixo, sem paginação — mesma simplicidade de outras
    # listagens administrativas do projeto.
    registros = await listar_escalonamentos(session)
    return [EscalonamentoResponse.model_validate(registro) for registro in registros]
