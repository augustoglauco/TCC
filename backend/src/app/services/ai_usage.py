"""Ledger unificado de uso de IA (origem × ambiente × modelo) — ver
docs/superpowers/specs/2026-10-08-ledger-uso-ia-origem-ambiente-modelo-design.md.

Todo ponto do sistema que usa um modelo/engine de IA (local ou externo,
texto ou visão) chama `registrar_uso_ia`. Mesmo padrão de sessão de
`app.services.ingestion_metrics.record_ingestion_cost` (sessão explícita /
sessão própria via factory / fallback para um sessionmaker global
configurado uma vez em `app.main`) — reaproveitado de propósito em vez de
inventar uma convenção nova; os dois serviços continuam independentes
(decisão sobre unificá-los fica para quando a origem "admin" for
conectada, ver spec §6).
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import AiUsageEvent

logger = logging.getLogger("assistente.ai_usage")

_global_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def set_global_sessionmaker(sessionmaker: async_sessionmaker[AsyncSession] | None) -> None:
    """Configura o sessionmaker global usado quando nenhuma sessão/factory
    explícita é passada — chamado uma vez em `app.main` (lifespan)."""
    global _global_sessionmaker
    _global_sessionmaker = sessionmaker


async def registrar_uso_ia(
    *,
    origem: str,
    ambiente: str,
    modelo: str,
    operacao: str,
    tokens_entrada: int = 0,
    tokens_saida: int = 0,
    custo_usd: float = 0.0,
    referencia_id: str | None = None,
    session: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    commit: bool = False,
) -> AiUsageEvent | None:
    """Registra um evento de uso de IA. Nunca lança exceção: falha de
    banco (ou nenhuma sessão disponível) vira `logger.warning` e `None` —
    telemetria não pode derrubar a chamada de IA real que ela registra."""
    evento = AiUsageEvent(
        origem=origem,
        ambiente=ambiente,
        modelo=modelo,
        operacao=operacao,
        tokens_entrada=tokens_entrada,
        tokens_saida=tokens_saida,
        custo_usd=round(custo_usd, 6),
        referencia_id=referencia_id,
    )

    try:
        if session is not None:
            session.add(evento)
            if commit:
                await session.commit()
            else:
                await session.flush()
            return evento

        factory = session_factory or _global_sessionmaker
        if factory is not None:
            async with factory() as s:
                s.add(evento)
                await s.commit()
                return evento
    except Exception as exc:
        logger.warning(
            "Falha ao registrar AiUsageEvent (origem=%s, operacao=%s): %s",
            origem,
            operacao,
            exc,
        )
    return None
