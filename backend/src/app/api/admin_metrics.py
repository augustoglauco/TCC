"""Endpoints administrativos de métricas de tokens, custos e chats encerrados."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.db.models import Conversa, ConversaMensagem

logger = logging.getLogger("assistente.admin_metrics")

router = APIRouter(prefix="/api/admin/metrics", tags=["Admin Metricas"])


class MetricSummary(BaseModel):
    total_closed_chats: int = 0
    total_internal_prompt_tokens: int = 0
    total_internal_completion_tokens: int = 0
    total_external_prompt_tokens: int = 0
    total_external_completion_tokens: int = 0
    total_cost_prompt_usd: float = 0.0
    total_cost_completion_usd: float = 0.0
    total_cost_usd: float = 0.0


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
) -> TokenCostMetricsResponse:
    """Retorna sumário e relatório diário de tokens e custos para chats encerrados."""
    session_factory = getattr(request.app.state, "db_sessionmaker", None)
    if not session_factory:
        raise HTTPException(status_code=503, detail="Banco de dados não configurado.")

    now = datetime.now(UTC)
    cutoff_start: datetime | None = None
    cutoff_end: datetime | None = None

    if start_date:
        try:
            dt = datetime.fromisoformat(start_date)
            cutoff_start = datetime(dt.year, dt.month, dt.day, 0, 0, 0, tzinfo=UTC)
        except ValueError:
            pass

    if end_date:
        try:
            dt = datetime.fromisoformat(end_date)
            cutoff_end = datetime(dt.year, dt.month, dt.day, 23, 59, 59, 999999, tzinfo=UTC)
        except ValueError:
            pass

    if cutoff_start is None and cutoff_end is None:
        if period == "today":
            cutoff_start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=UTC)
        elif period == "7d":
            cutoff_start = now - timedelta(days=7)
        elif period == "30d":
            cutoff_start = now - timedelta(days=30)
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

    if cutoff_start is not None:
        stmt = stmt.where(Conversa.encerrada_em >= cutoff_start)
    if cutoff_end is not None:
        stmt = stmt.where(Conversa.encerrada_em <= cutoff_end)

    try:
        async with session_factory() as session:
            result = await session.execute(stmt)
            rows = result.all()
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

    daily_map: dict[str, dict[str, Any]] = {}

    for conv_id, encerrada_em, metricas in rows:
        total_closed_chats_set.add(conv_id)
        if encerrada_em is None:
            continue
        dt = encerrada_em if encerrada_em.tzinfo else encerrada_em.replace(tzinfo=UTC)
        date_key = dt.strftime("%Y-%m-%d")

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

            if backend_used == "externo":
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
    )

    return TokenCostMetricsResponse(
        period=period,
        summary=summary,
        daily_breakdown=daily_breakdown,
    )
