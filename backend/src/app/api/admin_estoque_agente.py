"""Estado do agente autônomo de estoque (R13) para o indicador do catálogo de
produtos (`/admin/produtos`)."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.estoque_preditivo import AGENTE_DETERMINISTICO, AGENTE_IA
from app.agents.execucoes import ultima_execucao, ultimo_alerta_em
from app.agents.runtime import runtime
from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session

router = APIRouter(
    prefix="/api/admin/agentes/estoque",
    tags=["Admin Agente de Estoque"],
    dependencies=[Depends(require_admin)],
)


class ExecucaoOut(BaseModel):
    criado_em: datetime | None
    modo: str
    produtos_avaliados: int
    alertas_criados: int
    erro: str | None


class StatusAgenteEstoque(BaseModel):
    modo: str
    llm: str | None
    ultima_execucao: ExecucaoOut | None
    ultimo_alerta_em: datetime | None


@router.get("/status", response_model=StatusAgenteEstoque)
async def status_agente_estoque(
    session: AsyncSession = Depends(get_db_session),
) -> StatusAgenteEstoque:
    """Modo atual, última avaliação e último alerta. O agente só roda quando um
    pedido é criado, então "sem avaliação" significa "ainda não houve pedido",
    não necessariamente que ele esteja parado."""
    execucao = await ultima_execucao(session)
    return StatusAgenteEstoque(
        modo=runtime.estoque_modo,
        llm=runtime.estoque_llm if runtime.estoque_modo == "ia" else None,
        ultima_execucao=(
            ExecucaoOut.model_validate(execucao, from_attributes=True) if execucao else None
        ),
        ultimo_alerta_em=await ultimo_alerta_em(session, [AGENTE_DETERMINISTICO, AGENTE_IA]),
    )
