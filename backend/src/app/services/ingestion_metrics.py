"""Serviço para registro e auditoria de consumo e custos de modelos externos
em operações de ingestão, crawler e catálogo de produtos.
"""

import logging
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import IngestionCostEvent

logger = logging.getLogger("assistente.ingestion_metrics")

_global_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def set_global_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession] | None) -> None:
    """Configura o sessionmaker global utilizado quando nenhuma sessão explícita é passada."""
    global _global_sessionmaker
    _global_sessionmaker = sessionmaker


def _get_fallback_sessionmaker() -> async_sessionmaker[AsyncSession] | None:
    global _global_sessionmaker
    if _global_sessionmaker is not None:
        return _global_sessionmaker

    try:
        from app.config import get_settings
        from app.db.engine import create_db_engine, create_session_factory

        settings = get_settings()
        engine = create_db_engine(settings.database_url)
        _global_sessionmaker = create_session_factory(engine)
        return _global_sessionmaker
    except Exception as exc:
        logger.warning("Não foi possível criar sessionmaker de fallback para métricas de ingestão: %s", exc)
        return None


async def record_ingestion_cost(
    source_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cost_prompt_usd: float = 0.0,
    cost_completion_usd: float = 0.0,
    total_cost_usd: float = 0.0,
    source_identifier: str | None = None,
    model_name: str | None = None,
    session: AsyncSession | None = None,
) -> IngestionCostEvent | None:
    """Registra um evento de telemetria e custo gerado por modelo externo
    em pipeline de dados (crawler, extração de catálogo, etc).
    """
    total = total_cost_usd if total_cost_usd > 0 else (cost_prompt_usd + cost_completion_usd)

    event = IngestionCostEvent(
        source_type=source_type,
        source_identifier=source_identifier,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_prompt_usd=round(cost_prompt_usd, 6),
        cost_completion_usd=round(cost_completion_usd, 6),
        total_cost_usd=round(total, 6),
    )

    try:
        if session is not None:
            session.add(event)
            await session.flush()
            return event

        factory = _get_fallback_sessionmaker()
        if factory is not None:
            async with factory() as s:
                s.add(event)
                await s.commit()
                return event
    except Exception as exc:
        logger.warning(
            "Falha ao registrar IngestionCostEvent (source_type=%s, source=%s): %s",
            source_type,
            source_identifier,
            exc,
        )

    return None
