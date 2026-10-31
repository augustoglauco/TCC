"""Registro e consulta das avaliações do agente de estoque (R13).

Cada rodada de `avaliar_estoque` grava uma linha em `agente_execucoes`, com ou
sem alerta, para o catálogo mostrar que o agente está habilitado e quando rodou
pela última vez. Falha ao gravar o registro nunca derruba a avaliação.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgenteExecucao, MensagemAgente

logger = logging.getLogger("assistente.agents.execucoes")

AGENTE_ESTOQUE = "estoque"
# Cabe no `Text`, mas evita despejar um traceback inteiro na tela do admin.
_ERRO_MAX_CHARS = 500


async def registrar_execucao(
    session: AsyncSession,
    *,
    modo: str,
    produtos_avaliados: int,
    alertas_criados: int,
    erro: str | None = None,
) -> None:
    try:
        session.add(
            AgenteExecucao(
                agente=AGENTE_ESTOQUE,
                modo=modo,
                produtos_avaliados=produtos_avaliados,
                alertas_criados=alertas_criados,
                erro=erro[:_ERRO_MAX_CHARS] if erro else None,
            )
        )
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.exception("Falha ao registrar a execução do agente de estoque")


async def ultima_execucao(session: AsyncSession) -> AgenteExecucao | None:
    return await session.scalar(
        select(AgenteExecucao)
        .where(AgenteExecucao.agente == AGENTE_ESTOQUE)
        .order_by(AgenteExecucao.criado_em.desc())
        .limit(1)
    )


async def ultimo_alerta_em(session: AsyncSession, agentes: list[str]) -> datetime | None:
    return await session.scalar(
        select(MensagemAgente.criado_em)
        .where(MensagemAgente.agente.in_(agentes))
        .order_by(MensagemAgente.criado_em.desc())
        .limit(1)
    )
