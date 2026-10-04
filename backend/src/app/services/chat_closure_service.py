"""Serviço de encerramento de conversas (manual e automático por inatividade)."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Conversa

logger = logging.getLogger("assistente.chat_closure")


async def fechar_conversas_inativas(session: AsyncSession, timeout_minutes: int = 30) -> int:
    """Encerra conversas com status='aberta' cuja última atualização foi há
    mais de `timeout_minutes` minutos.

    Retorna a quantidade de conversas encerradas.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
    now = datetime.now(UTC)

    stmt = (
        update(Conversa)
        .where(Conversa.status == "aberta")
        .where(Conversa.atualizada_em < cutoff)
        .values(
            status="encerrada",
            encerrada_em=now,
            motivo_encerramento="inatividade",
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    closed_count = result.rowcount or 0
    if closed_count > 0:
        logger.info("Encerradas %d conversas inativas (> %d min)", closed_count, timeout_minutes)
    return closed_count


async def fechar_conversa(
    session: AsyncSession, conversation_id: str, motivo: str = "manual_usuario"
) -> Conversa | None:
    """Encerra uma conversa específica pelo ID.

    Operação idempotente: se já estiver encerrada, devolve a conversa sem alterar.
    Se não existir, devolve None.
    """
    stmt = select(Conversa).where(Conversa.id == conversation_id)
    result = await session.execute(stmt)
    conversa = result.scalar_one_or_none()
    if conversa is None:
        return None

    if conversa.status == "encerrada":
        return conversa

    conversa.status = "encerrada"
    conversa.encerrada_em = datetime.now(UTC)
    conversa.motivo_encerramento = motivo
    await session.commit()
    await session.refresh(conversa)
    logger.info("Conversa %s encerrada manualmente (motivo: %s)", conversation_id, motivo)
    return conversa


async def inactivity_closure_worker(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    interval_seconds: int = 300,
    timeout_minutes: int = 30,
) -> None:
    """Worker em background executado periodicamente para fechar conversas inativas."""
    logger.info(
        "Inactivity closure worker iniciado (intervalo: %ds, timeout: %d min)",
        interval_seconds,
        timeout_minutes,
    )
    try:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                async with db_sessionmaker() as session:
                    await fechar_conversas_inativas(session, timeout_minutes=timeout_minutes)
            except Exception as exc:
                logger.warning("Erro no worker de encerramento de conversas inativas: %s", exc)
    except asyncio.CancelledError:
        logger.info("Inactivity closure worker cancelado.")
