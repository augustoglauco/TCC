"""Chaves de acesso ao MCP B2B geradas pelo Admin (R12, decisão de 2026-11-05).

O texto da chave nunca é guardado: só o SHA-256 (a chave é aleatória e longa, então
um hash simples basta). Gerar uma chave nova revoga as anteriores do mesmo cliente.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChaveParceiro, Cliente

_PREFIXO_CHAVE = "b2b_"
_TAMANHO_PREFIXO_EXIBIDO = 10


def hash_da_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


async def gerar_chave(session: AsyncSession, cliente: Cliente) -> tuple[str, ChaveParceiro]:
    """Gera a chave do cliente, revoga as ativas e devolve `(texto, registro)`.
    O texto só existe neste retorno."""
    agora = datetime.now(UTC)
    ativas = await session.scalars(
        select(ChaveParceiro).where(
            ChaveParceiro.cliente_id == cliente.id, ChaveParceiro.revogada_em.is_(None)
        )
    )
    for antiga in ativas:
        antiga.revogada_em = agora
    chave = _PREFIXO_CHAVE + secrets.token_urlsafe(32)
    registro = ChaveParceiro(
        cliente_id=cliente.id,
        prefixo=chave[:_TAMANHO_PREFIXO_EXIBIDO],
        chave_hash=hash_da_chave(chave),
    )
    session.add(registro)
    await session.commit()
    await session.refresh(registro)
    return chave, registro


async def revogar_chaves(session: AsyncSession, cliente_id: int) -> int:
    """Revoga as chaves ativas do cliente; devolve quantas foram revogadas."""
    agora = datetime.now(UTC)
    ativas = list(
        await session.scalars(
            select(ChaveParceiro).where(
                ChaveParceiro.cliente_id == cliente_id, ChaveParceiro.revogada_em.is_(None)
            )
        )
    )
    for chave in ativas:
        chave.revogada_em = agora
    await session.commit()
    return len(ativas)


async def listar_chaves_ativas(session: AsyncSession) -> list[tuple[ChaveParceiro, Cliente]]:
    linhas = await session.execute(
        select(ChaveParceiro, Cliente)
        .join(Cliente, Cliente.id == ChaveParceiro.cliente_id)
        .where(ChaveParceiro.revogada_em.is_(None))
        .order_by(ChaveParceiro.criada_em.desc())
    )
    return [(chave, cliente) for chave, cliente in linhas.all()]


async def email_do_parceiro_da_chave(session: AsyncSession, chave: str) -> str | None:
    """E-mail do cliente dono de uma chave ativa, ou `None` se desconhecida/revogada."""
    return await session.scalar(
        select(Cliente.email)
        .join(ChaveParceiro, ChaveParceiro.cliente_id == Cliente.id)
        .where(
            ChaveParceiro.chave_hash == hash_da_chave(chave),
            ChaveParceiro.revogada_em.is_(None),
        )
    )
