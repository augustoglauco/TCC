"""Ciclo de vida de uma proposta: criar → confirmar/cancelar/expirar, com auditoria."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa, PropostaInvalidaError
from app.db.models import ChatAdminAcao

PROPOSTA_TTL = timedelta(minutes=10)


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
        await _encerrar(session, acao, "expirada")
        raise PropostaInvalidaError("Proposta expirada; peça de novo.")
    return acao


async def _encerrar(session: AsyncSession, acao: ChatAdminAcao, status: str) -> None:
    """Muda `proposta` → `status` por UPDATE condicional: nunca sobrescreve `executada`."""
    resultado = await session.execute(
        update(ChatAdminAcao)
        .where(ChatAdminAcao.id == acao.id, ChatAdminAcao.status == "proposta")
        .values(status=status)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    if resultado.rowcount == 0:
        raise PropostaInvalidaError("Proposta já resolvida.")
    await session.refresh(acao)


async def _reivindicar(session: AsyncSession, acao_id: uuid.UUID) -> None:
    """Reivindica a proposta de forma atômica (`proposta` → `executando`) antes de executar.

    O status `executando` só existe dentro da transação: o commit final grava `executada` e
    qualquer falha faz rollback, voltando a `proposta`. Quem perde a corrida não casa a linha.
    """
    resultado = await session.execute(
        update(ChatAdminAcao)
        .where(ChatAdminAcao.id == acao_id, ChatAdminAcao.status == "proposta")
        .values(status="executando")
        .execution_options(synchronize_session=False)
    )
    if resultado.rowcount == 0:
        raise PropostaInvalidaError("Proposta já em execução ou resolvida.")


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
        await _reivindicar(session, acao.id)
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
    await _encerrar(session, acao, "cancelada")
    return acao
