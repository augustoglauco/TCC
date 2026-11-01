"""Ponto de entrada das ferramentas do Admin para o orquestrador do chat."""

import logging
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.admin_tools.consulta import executar_consulta, gerar_sql
from app.admin_tools.intencao import detectar_consulta
from app.models.chat import CardTabela
from app.services.safe_sql import SQLSecurityError, get_catalog_schema_prompt

logger = logging.getLogger(__name__)

LIMITE_LINHAS = 50


def _card_tabela(linhas: list[dict[str, Any]]) -> CardTabela:
    colunas = list(linhas[0].keys()) if linhas else []
    return CardTabela(
        titulo="Resultado da consulta",
        colunas=colunas,
        linhas=[[linha[c] for c in colunas] for linha in linhas],
        truncado=len(linhas) >= LIMITE_LINHAS,
    )


async def _consultar(message: str, local_client: Any, db_sessionmaker: Any):
    """Retorna (texto, card): o card é None quando a consulta não pôde ser feita."""
    async with db_sessionmaker() as session:
        try:
            sql = await gerar_sql(local_client, message, await get_catalog_schema_prompt(session))
        except Exception as exc:  # fronteira de isolamento: LLM/esquema fora não derruba o turno
            logger.exception("falha_ao_gerar_sql_admin")
            return _falha(exc), None
        if sql is None:
            return "Não consegui montar uma consulta para esse pedido. Reformule, por favor.", None
        try:
            linhas = await executar_consulta(session, sql)
        except SQLSecurityError as exc:
            return f"Essa consulta não é permitida: {exc}", None
        except SQLAlchemyError as exc:
            logger.warning("falha_ao_executar_consulta_admin", extra={"erro": str(exc)})
            await session.rollback()
            return _falha(exc), None
    if not linhas:
        return "A consulta não retornou nenhuma linha.", None
    return f"Encontrei {len(linhas)} linha(s).", _card_tabela(linhas)


def _falha(exc: Exception) -> str:
    motivo = (str(exc).splitlines() or [type(exc).__name__])[0][:200]
    return f"A consulta falhou: {motivo}. Reformule o pedido."


async def processar_pedido_admin(
    message: str,
    *,
    is_admin: bool,
    local_client: Any,
    db_sessionmaker: Any,
    intent_router_provider: str,
) -> AsyncIterator[Any]:
    """Emite os eventos de uma ferramenta do Admin; não emite nada se o texto não é um pedido
    de ferramenta ou se o usuário não é Admin (o chat segue o fluxo normal)."""
    from app.router.orchestrator import (  # import tardio: evita ciclo com o orquestrador
        RouterDecision,
        TokenEvent,
        _emitir_chart_decision_base,
    )

    if not is_admin or db_sessionmaker is None or not detectar_consulta(message):
        return
    texto, card = await _consultar(message, local_client, db_sessionmaker)
    yield TokenEvent(text=texto)
    yield RouterDecision(
        **_emitir_chart_decision_base(intent_router_provider, None, None),
        resposta=texto,
        card=card,
    )
