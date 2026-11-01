"""Ciclo de vida de uma proposta: criar → confirmar/cancelar/expirar, com auditoria."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa
from app.db.models import ChatAdminAcao

PROPOSTA_TTL = timedelta(minutes=10)


class PropostaInvalidaError(Exception):
    """Proposta inexistente, de outro admin, expirada ou já resolvida."""


def _agora(agora: datetime | None) -> datetime:
    return agora or datetime.now(UTC)


async def criar_proposta(
    session: AsyncSession,
    *,
    admin_id: int,
    ferramenta: str,
    argumentos: dict,
    agora: datetime | None = None,
) -> tuple[ChatAdminAcao, Previa]:
    """Valida via `preparar` e grava a proposta; nada é executado aqui."""
    impl = FERRAMENTAS.get(ferramenta)
    if impl is None:
        raise PropostaInvalidaError(f"Ferramenta desconhecida: {ferramenta}.")
    previa = await impl.preparar(session, argumentos)
    momento = _agora(agora)
    acao = ChatAdminAcao(
        admin_id=admin_id,
        ferramenta=ferramenta,
        argumentos=argumentos,
        antes=previa.antes,
        depois=previa.depois,
        aviso=previa.aviso,
        status="proposta",
        expira_em=momento + PROPOSTA_TTL,
    )
    session.add(acao)
    await session.commit()
    return acao, previa


async def _carregar_pendente(
    session: AsyncSession, acao_id: uuid.UUID, admin_id: int, agora: datetime
) -> ChatAdminAcao:
    acao = await session.get(ChatAdminAcao, acao_id)
    if acao is None or acao.admin_id != admin_id:
        raise PropostaInvalidaError("Proposta não encontrada.")
    if acao.status != "proposta":
        raise PropostaInvalidaError(f"Proposta já {acao.status}.")
    expira = acao.expira_em if acao.expira_em.tzinfo else acao.expira_em.replace(tzinfo=UTC)
    if agora > expira:
        acao.status = "expirada"
        await session.commit()
        raise PropostaInvalidaError("Proposta expirada; peça de novo.")
    return acao


async def confirmar(
    session: AsyncSession, acao_id: uuid.UUID, *, admin_id: int, agora: datetime | None = None
) -> ChatAdminAcao:
    """Revalida (`preparar` de novo) e executa na mesma transação do registro de auditoria.

    `executar` NÃO faz commit: o commit abaixo grava a escrita e a auditoria juntas. Qualquer
    falha (`preparar`/`executar`) desfaz a sessão e a proposta continua pendente.
    """
    momento = _agora(agora)
    acao = await _carregar_pendente(session, acao_id, admin_id, momento)
    impl = FERRAMENTAS[acao.ferramenta]
    try:
        await impl.preparar(session, acao.argumentos)
        acao.depois = await impl.executar(session, acao.argumentos, admin_id=admin_id)
        acao.status = "executada"
        acao.executado_em = momento
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    return acao


async def cancelar(session: AsyncSession, acao_id: uuid.UUID, *, admin_id: int) -> ChatAdminAcao:
    acao = await _carregar_pendente(session, acao_id, admin_id, _agora(None))
    acao.status = "cancelada"
    await session.commit()
    return acao
