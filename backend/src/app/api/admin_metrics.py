"""Endpoints administrativos de métricas de tokens, custos e chats encerrados."""

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import verificar_admin_por_token
from app.api.rag_dependencies import get_db_session
from app.config import get_settings
from app.db.models import Conversa, ConversaMensagem, IngestionCostEvent

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


class MetricSummary(BaseModel):
    total_closed_chats: int = 0
    total_internal_prompt_tokens: int = 0
    total_internal_completion_tokens: int = 0
    total_external_prompt_tokens: int = 0
    total_external_completion_tokens: int = 0
    total_cost_prompt_usd: float = 0.0
    total_cost_completion_usd: float = 0.0
    total_cost_usd: float = 0.0
    total_vision_calls: int = 0
    total_vision_tokens: int = 0
    total_vision_cost_usd: float = 0.0
    total_ingestion_calls: int = 0
    total_ingestion_tokens: int = 0
    total_ingestion_cost_usd: float = 0.0
    grand_total_cost_usd: float = 0.0


class DailyMetric(BaseModel):
    date: str
    closed_chats_count: int = 0
    internal_prompt_tokens: int = 0
    internal_completion_tokens: int = 0
    external_prompt_tokens: int = 0
    external_completion_tokens: int = 0
    cost_prompt_usd: float = 0.0
    cost_completion_usd: float = 0.0
    total_cost_usd: float = 0.0
    vision_calls_count: int = 0
    vision_cost_usd: float = 0.0
    ingestion_calls_count: int = 0
    ingestion_cost_usd: float = 0.0


class TokenCostMetricsResponse(BaseModel):
    period: str
    summary: MetricSummary
    daily_breakdown: list[DailyMetric]


@router.get("/tokens-and-costs", response_model=TokenCostMetricsResponse)
async def get_token_and_cost_metrics(
    request: Request,
    period: str = Query("7d", description="Período: 'today', '7d', '30d' ou 'all'"),
    start_date: str | None = Query(None, description="Data inicial ISO YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Data final ISO YYYY-MM-DD"),
    _: None = Depends(require_admin),
) -> TokenCostMetricsResponse:
    """Retorna sumário e relatório diário de tokens e custos para chats encerrados."""
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")

    # Achado da revisão de 2026-10-04: "hoje"/`start_date`/`end_date` são
    # conceitos de calendário LOCAL do administrador, não UTC — bucketar em
    # UTC fazia o filtro "Hoje" e o agrupamento diário cortarem o dia às
    # 21h (horário de Brasília) em vez da meia-noite local. Reaproveita o
    # mesmo fuso já configurado para o Agendamento (`agendamento_timezone`)
    # em vez de introduzir uma config nova só para isto.
    local_tz = ZoneInfo(get_settings().agendamento_timezone)
    now_local = datetime.now(local_tz)
    cutoff_start: datetime | None = None
    cutoff_end: datetime | None = None

    if start_date:
        try:
            d = date.fromisoformat(start_date)
            cutoff_start = datetime(
                d.year, d.month, d.day, 0, 0, 0, tzinfo=local_tz
            ).astimezone(UTC)
        except ValueError as exc:
            # Achado da revisão de 2026-10-04: antes, uma data mal formada
            # era silenciosamente ignorada e a resposta caía no período
            # default (ex.: 7d) sem avisar o administrador — parecendo um
            # filtro aplicado quando na verdade foi outro, bem diferente.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"start_date inválida ({start_date!r}); use o formato YYYY-MM-DD.",
            ) from exc

    if end_date:
        try:
            d = date.fromisoformat(end_date)
            cutoff_end = datetime(
                d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=local_tz
            ).astimezone(UTC)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"end_date inválida ({end_date!r}); use o formato YYYY-MM-DD.",
            ) from exc

    if cutoff_start is None and cutoff_end is None:
        if period == "today":
            local_midnight = datetime(
                now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=local_tz
            )
            cutoff_start = local_midnight.astimezone(UTC)
        elif period == "7d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=7)
        elif period == "30d":
            cutoff_start = now_local.astimezone(UTC) - timedelta(days=30)
        elif period == "all":
            cutoff_start = None

    stmt = (
        select(
            Conversa.id,
            Conversa.encerrada_em,
            ConversaMensagem.metricas,
        )
        .outerjoin(
            ConversaMensagem,
            (Conversa.id == ConversaMensagem.conversa_id) & (ConversaMensagem.papel == "assistente"),
        )
        .where(Conversa.status == "encerrada")
        .where(Conversa.encerrada_em.is_not(None))
    )

    stmt_ingest = (
        select(
            IngestionCostEvent.criado_em,
            IngestionCostEvent.prompt_tokens,
            IngestionCostEvent.completion_tokens,
            IngestionCostEvent.total_cost_usd,
        )
        .order_by(IngestionCostEvent.criado_em.desc())
    )

    if cutoff_start is not None:
        stmt = stmt.where(Conversa.encerrada_em >= cutoff_start)
        stmt_ingest = stmt_ingest.where(IngestionCostEvent.criado_em >= cutoff_start)
    if cutoff_end is not None:
        stmt = stmt.where(Conversa.encerrada_em <= cutoff_end)
        stmt_ingest = stmt_ingest.where(IngestionCostEvent.criado_em <= cutoff_end)

    try:
        async with session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()

            try:
                ingest_res = await session.execute(stmt_ingest)
                ingest_rows = ingest_res.all()
            except Exception as e_ingest:
                logger.warning("Falha ao consultar ingestion_cost_events: %s", e_ingest)
                ingest_rows = []
    except Exception as exc:
        logger.error("Erro ao consultar métricas de conversas no banco: %s", exc)
        raise HTTPException(status_code=503, detail="Erro ao consultar métricas.") from exc

    total_closed_chats_set: set[str] = set()
    total_internal_prompt = 0
    total_internal_comp = 0
    total_external_prompt = 0
    total_external_comp = 0
    total_cost_prompt = 0.0
    total_cost_comp = 0.0
    total_cost = 0.0
    total_vision_calls = 0
    total_vision_tokens = 0
    total_vision_cost = 0.0
    total_ingestion_calls = 0
    total_ingestion_tokens = 0
    total_ingestion_cost = 0.0

    daily_map: dict[str, dict[str, Any]] = {}

    for conv_id, encerrada_em, metricas in rows:
        total_closed_chats_set.add(conv_id)
        if encerrada_em is None:
            continue
        dt = encerrada_em if encerrada_em.tzinfo else encerrada_em.replace(tzinfo=UTC)
        date_key = dt.astimezone(local_tz).strftime("%Y-%m-%d")

        if date_key not in daily_map:
            daily_map[date_key] = {
                "date": date_key,
                "chats_set": set(),
                "internal_prompt_tokens": 0,
                "internal_completion_tokens": 0,
                "external_prompt_tokens": 0,
                "external_completion_tokens": 0,
                "cost_prompt_usd": 0.0,
                "cost_completion_usd": 0.0,
                "total_cost_usd": 0.0,
                "vision_calls_count": 0,
                "vision_cost_usd": 0.0,
                "ingestion_calls_count": 0,
                "ingestion_cost_usd": 0.0,
            }

        daily = daily_map[date_key]
        daily["chats_set"].add(conv_id)

        if isinstance(metricas, dict):
            backend_used = metricas.get("backend_used")
            p_tok = int(metricas.get("prompt_tokens") or 0)
            c_tok = int(metricas.get("completion_tokens") or 0)
            c_prompt = float(metricas.get("cost_prompt_usd") or 0.0)
            c_comp = float(metricas.get("cost_completion_usd") or 0.0)
            c_tot = float(metricas.get("estimated_cost_usd") or (c_prompt + c_comp))
            is_vision = bool(
                metricas.get("vision_used")
                or (backend_used == "identificacao_imagem")
                or (
                    backend_used == "externo"
                    and metricas.get("model_name")
                    and any(m in str(metricas.get("model_name")).lower() for m in ["gemma", "gemini-flash", "vision", "vl"])
                    and c_prompt > 0
                )
            )

            if is_vision:
                total_vision_calls += 1
                total_vision_tokens += (p_tok + c_tok)
                total_vision_cost += c_tot
                daily["vision_calls_count"] += 1
                daily["vision_cost_usd"] += c_tot

            if backend_used in ("externo", "openrouter") or c_tot > 0:
                total_external_prompt += p_tok
                total_external_comp += c_tok
                total_cost_prompt += c_prompt
                total_cost_comp += c_comp
                total_cost += c_tot

                daily["external_prompt_tokens"] += p_tok
                daily["external_completion_tokens"] += c_tok
                daily["cost_prompt_usd"] += c_prompt
                daily["cost_completion_usd"] += c_comp
                daily["total_cost_usd"] += c_tot
            else:
                total_internal_prompt += p_tok
                total_internal_comp += c_tok

                daily["internal_prompt_tokens"] += p_tok
                daily["internal_completion_tokens"] += c_tok

    # Acumula eventos de custo de ingestão (crawler, catálogo, etc)
    for criado_em, p_tok, c_tok, c_tot in ingest_rows:
        p_tok = int(p_tok or 0)
        c_tok = int(c_tok or 0)
        c_tot = float(c_tot or 0.0)

        total_ingestion_calls += 1
        total_ingestion_tokens += (p_tok + c_tok)
        total_ingestion_cost += c_tot

        if criado_em is None:
            continue
        dt = criado_em if criado_em.tzinfo else criado_em.replace(tzinfo=UTC)
        date_key = dt.astimezone(local_tz).strftime("%Y-%m-%d")

        if date_key not in daily_map:
            daily_map[date_key] = {
                "date": date_key,
                "chats_set": set(),
                "internal_prompt_tokens": 0,
                "internal_completion_tokens": 0,
                "external_prompt_tokens": 0,
                "external_completion_tokens": 0,
                "cost_prompt_usd": 0.0,
                "cost_completion_usd": 0.0,
                "total_cost_usd": 0.0,
                "vision_calls_count": 0,
                "vision_cost_usd": 0.0,
                "ingestion_calls_count": 0,
                "ingestion_cost_usd": 0.0,
            }

        daily = daily_map[date_key]
        daily["ingestion_calls_count"] += 1
        daily["ingestion_cost_usd"] += c_tot

    daily_breakdown = [
        DailyMetric(
            date=d["date"],
            closed_chats_count=len(d["chats_set"]),
            internal_prompt_tokens=d["internal_prompt_tokens"],
            internal_completion_tokens=d["internal_completion_tokens"],
            external_prompt_tokens=d["external_prompt_tokens"],
            external_completion_tokens=d["external_completion_tokens"],
            cost_prompt_usd=round(d["cost_prompt_usd"], 6),
            cost_completion_usd=round(d["cost_completion_usd"], 6),
            total_cost_usd=round(d["total_cost_usd"], 6),
            vision_calls_count=d.get("vision_calls_count", 0),
            vision_cost_usd=round(d.get("vision_cost_usd", 0.0), 6),
            ingestion_calls_count=d.get("ingestion_calls_count", 0),
            ingestion_cost_usd=round(d.get("ingestion_cost_usd", 0.0), 6),
        )
        for d in sorted(daily_map.values(), key=lambda x: x["date"], reverse=True)
    ]

    summary = MetricSummary(
        total_closed_chats=len(total_closed_chats_set),
        total_internal_prompt_tokens=total_internal_prompt,
        total_internal_completion_tokens=total_internal_comp,
        total_external_prompt_tokens=total_external_prompt,
        total_external_completion_tokens=total_external_comp,
        total_cost_prompt_usd=round(total_cost_prompt, 6),
        total_cost_completion_usd=round(total_cost_comp, 6),
        total_cost_usd=round(total_cost, 6),
        total_vision_calls=total_vision_calls,
        total_vision_tokens=total_vision_tokens,
        total_vision_cost_usd=round(total_vision_cost, 6),
        total_ingestion_calls=total_ingestion_calls,
        total_ingestion_tokens=total_ingestion_tokens,
        total_ingestion_cost_usd=round(total_ingestion_cost, 6),
        grand_total_cost_usd=round(total_cost + total_ingestion_cost, 6),
    )

    return TokenCostMetricsResponse(
        period=period,
        summary=summary,
        daily_breakdown=daily_breakdown,
    )
