"""Endpoints REST para gestão de Agendamentos (R11, Fase 7)."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.models import Agendamento
from app.mcp_client.google_calendar import CalendarClient, GoogleCalendarConnectionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agendamentos", tags=["agendamentos"])


def get_calendar_client(request: Request) -> CalendarClient:
    return request.app.state.calendar_client


class AgendamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_email: str
    nome_cliente: str
    telefone: str | None = None
    data_hora_inicio: datetime
    data_hora_fim: datetime
    descricao: str | None = None
    status: str
    origem: str
    google_event_id: str | None = None
    google_event_link: str | None = None
    conversation_id: str | None = None
    criado_em: datetime
    atualizado_em: datetime


class AgendamentoManualCreate(BaseModel):
    user_email: str
    nome_cliente: str
    telefone: str | None = None
    data_hora_inicio: datetime
    data_hora_fim: datetime | None = None
    descricao: str | None = None
    forcar_sem_validacao: bool = False


@router.get("/meus", response_model=list[AgendamentoOut])
async def listar_meus_agendamentos(
    user_email: str = Query(..., description="E-mail do usuário autenticado"),
    db: AsyncSession = Depends(get_db_session),
) -> list[AgendamentoOut]:
    """Retorna lista de agendamentos associados ao e-mail informado."""
    query = (
        select(Agendamento)
        .where(Agendamento.user_email == user_email)
        .order_by(Agendamento.data_hora_inicio.desc())
    )
    result = await db.execute(query)
    agendamentos = result.scalars().all()
    return [AgendamentoOut.model_validate(ag) for ag in agendamentos]


@router.post("/{id}/cancelar", response_model=AgendamentoOut)
async def cancelar_agendamento(
    id: UUID,
    user_email: str = Query(..., description="E-mail do solicitante"),
    db: AsyncSession = Depends(get_db_session),
    calendar_client: CalendarClient = Depends(get_calendar_client),
) -> AgendamentoOut:
    """Cancela um agendamento do usuário e desmarca o evento no Google Calendar."""
    query = select(Agendamento).where(Agendamento.id == id)
    result = await db.execute(query)
    agendamento = result.scalars().first()

    if not agendamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agendamento não encontrado.",
        )

    if agendamento.user_email != user_email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para cancelar este agendamento.",
        )

    if agendamento.status == "cancelado":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este agendamento já está cancelado.",
        )

    agendamento.status = "cancelado"

    if agendamento.google_event_id:
        try:
            await calendar_client.delete_event(agendamento.google_event_id)
        except Exception as exc:
            logger.warning(
                "falha_ao_remover_evento_google",
                extra={
                    "event_id": agendamento.google_event_id,
                    "agendamento_id": str(agendamento.id),
                    "erro": str(exc),
                },
            )

    await db.commit()
    await db.refresh(agendamento)
    return AgendamentoOut.model_validate(agendamento)


@router.get("/admin", response_model=list[AgendamentoOut])
async def admin_listar_agendamentos(
    filtro_email: str | None = Query(None, description="Filtro parcial por e-mail"),
    status: str | None = Query(None, description="Filtro por status (ex: confirmado, cancelado)"),
    data_inicio: datetime | None = Query(None, description="Data inicial"),
    data_fim: datetime | None = Query(None, description="Data final"),
    db: AsyncSession = Depends(get_db_session),
) -> list[AgendamentoOut]:
    """Retorna todos os agendamentos cadastrados com suporte a filtros."""
    query = select(Agendamento)

    if filtro_email:
        query = query.where(Agendamento.user_email.ilike(f"%{filtro_email}%"))
    if status:
        query = query.where(Agendamento.status == status)
    if data_inicio:
        query = query.where(Agendamento.data_hora_inicio >= data_inicio)
    if data_fim:
        query = query.where(Agendamento.data_hora_inicio <= data_fim)

    query = query.order_by(Agendamento.data_hora_inicio.desc())
    result = await db.execute(query)
    agendamentos = result.scalars().all()
    return [AgendamentoOut.model_validate(ag) for ag in agendamentos]


@router.post("/admin/manual", response_model=AgendamentoOut, status_code=status.HTTP_201_CREATED)
async def admin_criar_agendamento_manual(
    payload: AgendamentoManualCreate,
    db: AsyncSession = Depends(get_db_session),
    calendar_client: CalendarClient = Depends(get_calendar_client),
) -> AgendamentoOut:
    """Cria um agendamento manualmente pelo painel admin, sincronizando com o Google Calendar."""
    data_hora_fim = payload.data_hora_fim or (payload.data_hora_inicio + timedelta(minutes=30))

    if not payload.forcar_sem_validacao:
        try:
            disponivel = await calendar_client.is_time_available(
                payload.data_hora_inicio, data_hora_fim
            )
            if not disponivel:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Horário indisponível na agenda Google.",
                )
        except GoogleCalendarConnectionError as exc:
            logger.warning("mcp_calendar_indisponivel_ao_verificar", extra={"erro": str(exc)})
            # Se for falha de conexão e não foi forçado, repassa ou loga
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Serviço Google Calendar indisponível: {exc}",
            )

    google_event_id: str | None = None
    google_event_link: str | None = None

    try:
        google_event_id, google_event_link = await calendar_client.create_event(
            summary=f"Visita — {payload.nome_cliente}",
            start=payload.data_hora_inicio,
            end=data_hora_fim,
            attendee_email=payload.user_email,
            attendee_name=payload.nome_cliente,
            description=payload.descricao or "",
        )
    except Exception as exc:
        logger.warning(
            "falha_ao_criar_evento_google_manual",
            extra={"erro": str(exc), "email": payload.user_email},
        )

    novo_agendamento = Agendamento(
        user_email=payload.user_email,
        nome_cliente=payload.nome_cliente,
        telefone=payload.telefone,
        data_hora_inicio=payload.data_hora_inicio,
        data_hora_fim=data_hora_fim,
        descricao=payload.descricao,
        status="confirmado",
        origem="manual_admin",
        google_event_id=google_event_id or None,
        google_event_link=google_event_link or None,
    )
    db.add(novo_agendamento)
    await db.commit()
    await db.refresh(novo_agendamento)

    return AgendamentoOut.model_validate(novo_agendamento)


@router.get("/admin/google-events")
async def admin_consultar_eventos_google(
    time_min: datetime | None = Query(None),
    time_max: datetime | None = Query(None),
    calendar_client: CalendarClient = Depends(get_calendar_client),
) -> list[dict]:
    """Consulta diretamente a agenda corporativa no Google Calendar via MCP."""
    agora = datetime.now(timezone.utc)
    inicio = time_min or agora
    fim = time_max or (agora + timedelta(days=30))

    try:
        eventos = await calendar_client.list_events(inicio, fim)
        return eventos
    except Exception as exc:
        logger.error("falha_ao_listar_eventos_google", extra={"erro": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Não foi possível consultar os eventos no Google Calendar: {exc}",
        )
