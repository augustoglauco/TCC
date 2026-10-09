"""Endpoint administrativo de uso de IA, estratificado por origem ×
ambiente × modelo, sobre o ledger unificado `ai_usage_events` (item E, ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-item-e-painel-design.md).

Substituiu `GET /api/admin/metrics/tokens-and-costs`, que lia dois esquemas
diferentes (`ConversaMensagem.metricas` e `IngestionCostEvent`) e inferia
"isto é visão?" por heurística de nome de modelo. A dimensão que faltava
(`origem`) e a separação interno/externo agora são fatos gravados pelo
ledger, então a heurística foi removida — não portada.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verificar_admin_por_token
from app.api.rag_dependencies import get_db_session
from app.config import get_settings
from app.db.models import AiUsageEvent, Conversa
from app.services.ai_usage_report import (
    AiUsageReport,
    EventoDiario,
    LinhaAgregada,
    montar_relatorio,
)

logger = logging.getLogger("assistente.admin_metrics")

router = APIRouter(prefix="/api/admin/metrics", tags=["Admin Metricas"])

try:
    from app.api.admin_auth import require_admin
except ImportError:

    async def require_admin(
        session: AsyncSession = Depends(get_db_session),
        authorization: Annotated[str | None, Header()] = None,
        x_auth_token: Annotated[str | None, Header(alias="X-Auth-Token")] = None,
        token_param: Annotated[str | None, Query(alias="token")] = None,
    ) -> None:
        token: str | None = None
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
            elif len(parts) == 1:
                token = parts[0]
        elif x_auth_token:
            token = x_auth_token
        elif token_param:
            token = token_param

        if not token or not await verificar_admin_por_token(session, token):
            raise HTTPException(
                status_code=403,
                detail="Acesso restrito a administradores autenticados.",
            )


def _resolver_janela(
    period: str,
    start_date: str | None,
    end_date: str | None,
    local_tz: ZoneInfo,
) -> tuple[datetime | None, datetime | None]:
    """Converte o filtro do painel em limites UTC.

    "Hoje"/`start_date`/`end_date` são conceitos de calendário LOCAL do
    administrador, não UTC — bucketar em UTC fazia o filtro cortar o dia às
    21h (horário de Brasília) em vez da meia-noite local (achado da revisão
    de 2026-10-04). Reaproveita o fuso já configurado para o Agendamento
    (`agendamento_timezone`) em vez de introduzir uma config nova.

    Data mal formada é `400`, não um fallback silencioso para o período
    default — também achado de 2026-10-04: o administrador via um filtro
    aplicado que na verdade era outro, bem diferente.
    """
    cutoff_start: datetime | None = None
    cutoff_end: datetime | None = None

    if start_date:
        try:
            d = date.fromisoformat(start_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"start_date inválida ({start_date!r}); use o formato YYYY-MM-DD.",
            ) from exc
        cutoff_start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=local_tz).astimezone(UTC)

    if end_date:
        try:
            d = date.fromisoformat(end_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"end_date inválida ({end_date!r}); use o formato YYYY-MM-DD.",
            ) from exc
        cutoff_end = datetime(
            d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=local_tz
        ).astimezone(UTC)

    if cutoff_start is None and cutoff_end is None:
        now_local = datetime.now(local_tz)
        if period == "today":
            cutoff_start = datetime(
                now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=local_tz
            ).astimezone(UTC)
        elif period == "7d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=7)
        elif period == "30d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=30)
        # period == "all" (ou desconhecido): sem corte.

    return cutoff_start, cutoff_end


def _dia_local(dt: datetime, local_tz: ZoneInfo) -> str:
    dt = dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return dt.astimezone(local_tz).strftime("%Y-%m-%d")


@router.get("/ai-usage", response_model=AiUsageReport)
async def get_ai_usage_metrics(
    request: Request,
    period: str = Query("7d", description="Período: 'today', '7d', '30d' ou 'all'"),
    start_date: str | None = Query(None, description="Data inicial ISO YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Data final ISO YYYY-MM-DD"),
    _: None = Depends(require_admin),
) -> AiUsageReport:
    """Uso de IA do período, estratificado por origem × ambiente × modelo ×
    operação, mais o recorte diário e o volume de chats encerrados."""
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")

    local_tz = ZoneInfo(get_settings().agendamento_timezone)
    cutoff_start, cutoff_end = _resolver_janela(period, start_date, end_date, local_tz)

    # Q1 — agregação cross-dimensional no banco. `SUM()` devolve NULL
    # quando TODOS os valores do grupo são NULL, que é exatamente a
    # semântica desejada ("não medido"); nenhum COALESCE aqui, de
    # propósito. `COUNT(coluna)` ignora NULLs, então
    # `COUNT(*) - COUNT(custo_usd)` é a contagem de chamadas sem custo
    # medido.
    stmt_agregado = select(
        AiUsageEvent.origem,
        AiUsageEvent.ambiente,
        AiUsageEvent.modelo,
        AiUsageEvent.operacao,
        func.count().label("chamadas"),
        func.sum(AiUsageEvent.tokens_entrada).label("tokens_entrada"),
        func.sum(AiUsageEvent.tokens_saida).label("tokens_saida"),
        func.sum(AiUsageEvent.custo_usd).label("custo_usd"),
        (func.count() - func.count(AiUsageEvent.custo_usd)).label("sem_custo"),
    ).group_by(
        AiUsageEvent.origem,
        AiUsageEvent.ambiente,
        AiUsageEvent.modelo,
        AiUsageEvent.operacao,
    )

    # Q2 — recorte diário. O bucket é o dia do calendário LOCAL do
    # administrador e não existe expressão portável entre SQLite (testes) e
    # PostgreSQL (produção) para truncar um timestamp num fuso arbitrário
    # (`date_trunc(... AT TIME ZONE ...)` é PostgreSQL, `date(x, '-3
    # hours')` é SQLite), e `CAST(criado_em AS DATE)` reintroduziria o bug
    # do dia cortado às 21h. Por isso só estas cinco colunas vêm do banco e
    # o agrupamento por dia é feito em Python — escolha deliberada, não
    # descuido (ver spec §3.1).
    stmt_eventos = select(
        AiUsageEvent.criado_em,
        AiUsageEvent.origem,
        AiUsageEvent.tokens_entrada,
        AiUsageEvent.tokens_saida,
        AiUsageEvent.custo_usd,
    )

    # Chats encerrados: KPI de volume de atendimento, não de uso de IA —
    # continua exigindo `status == "encerrada"` e bucketado por
    # `encerrada_em`, porque é literalmente isso que a métrica mede.
    stmt_closed = (
        select(Conversa.id, Conversa.encerrada_em)
        .where(Conversa.status == "encerrada")
        .where(Conversa.encerrada_em.is_not(None))
    )

    if cutoff_start is not None:
        stmt_agregado = stmt_agregado.where(AiUsageEvent.criado_em >= cutoff_start)
        stmt_eventos = stmt_eventos.where(AiUsageEvent.criado_em >= cutoff_start)
        stmt_closed = stmt_closed.where(Conversa.encerrada_em >= cutoff_start)
    if cutoff_end is not None:
        stmt_agregado = stmt_agregado.where(AiUsageEvent.criado_em <= cutoff_end)
        stmt_eventos = stmt_eventos.where(AiUsageEvent.criado_em <= cutoff_end)
        stmt_closed = stmt_closed.where(Conversa.encerrada_em <= cutoff_end)

    try:
        async with session_factory() as session:
            linhas_res = await session.execute(stmt_agregado)
            eventos_res = await session.execute(stmt_eventos)
            closed_res = await session.execute(stmt_closed)

            linhas = [
                LinhaAgregada(
                    origem=row.origem,
                    ambiente=row.ambiente,
                    modelo=row.modelo,
                    operacao=row.operacao,
                    chamadas=row.chamadas,
                    tokens_entrada=row.tokens_entrada,
                    tokens_saida=row.tokens_saida,
                    custo_usd=row.custo_usd,
                    chamadas_sem_custo_medido=row.sem_custo,
                )
                for row in linhas_res.all()
            ]
            eventos_diarios = [
                EventoDiario(
                    data=_dia_local(row.criado_em, local_tz),
                    origem=row.origem,
                    tokens_entrada=row.tokens_entrada,
                    tokens_saida=row.tokens_saida,
                    custo_usd=row.custo_usd,
                )
                for row in eventos_res.all()
            ]
            closed_rows = closed_res.all()
    except Exception as exc:
        logger.error("Erro ao consultar métricas de uso de IA no banco: %s", exc)
        raise HTTPException(status_code=503, detail="Erro ao consultar métricas.") from exc

    chats_por_dia: dict[str, set[str]] = {}
    todos_chats: set[str] = set()
    for conv_id, encerrada_em in closed_rows:
        todos_chats.add(conv_id)
        chats_por_dia.setdefault(_dia_local(encerrada_em, local_tz), set()).add(conv_id)

    return montar_relatorio(
        period=period,
        linhas=linhas,
        eventos_diarios=eventos_diarios,
        chats_encerrados_total=len(todos_chats),
        chats_encerrados_por_dia={dia: len(ids) for dia, ids in chats_por_dia.items()},
    )
