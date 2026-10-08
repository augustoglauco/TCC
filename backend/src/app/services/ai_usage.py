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
    tokens_entrada: int | None = None,
    tokens_saida: int | None = None,
    custo_usd: float | None = None,
    referencia_id: str | None = None,
    session: AsyncSession | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    commit: bool = False,
) -> AiUsageEvent | None:
    """Registra um evento de uso de IA. Nunca lança exceção: falha de
    banco (ou nenhuma sessão disponível) vira `logger.warning` e `None` —
    telemetria não pode derrubar a chamada de IA real que ela registra.

    Quando `session` é passada explicitamente e `commit=False` (o default), o
    evento só é `flush()`ado — quem chama é responsável por commitar a
    própria transação; se a sessão fechar sem commit, o evento é perdido
    silenciosamente (a função já retornou um `AiUsageEvent` não-`None`,
    não há como saber disso de fora). Use `commit=True`, ou gerencie o
    commit você mesmo, se não tiver certeza.
    """
    try:
        evento = AiUsageEvent(
            origem=origem,
            ambiente=ambiente,
            modelo=modelo,
            operacao=operacao,
            tokens_entrada=tokens_entrada,
            tokens_saida=tokens_saida,
            custo_usd=round(custo_usd, 6) if custo_usd is not None else None,
            referencia_id=referencia_id,
        )
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
