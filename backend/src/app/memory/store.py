"""Memória da conversa no Postgres (R9, Fase 6) — ver decisão de 2026-09-25
em docs/ARCHITECTURE.md §5.

Substitui o histórico em memória de `app.api.chat`: cada troca (mensagem do
cliente + resposta do assistente) é gravada em `conversa_mensagens`, e o
histórico recente usado pelo roteador passa a vir daqui.

# MVP: um visitante = um navegador (conversation_id no localStorage), sem
# login; texto guardado sem política de retenção (ver §7 da arquitetura).
"""

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversa, ConversaMensagem

# Quantas mensagens do cliente o roteador recebe como contexto recente —
# mesmo número do histórico em memória que isto substitui.
MENSAGENS_RECENTES = 3

# Texto muito longo (ex.: OCR de imagem colado na mensagem) não precisa ir
# inteiro para o histórico.
_TEXTO_MAX_CHARS = 8000

PAPEL_CLIENTE = "cliente"
PAPEL_ASSISTENTE = "assistente"


@dataclass
class ContextoConversa:
    """O que o chat precisa saber da conversa antes de responder."""

    mensagens_recentes: list[str] = field(default_factory=list)
    resumo: str | None = None
    email: str | None = None


async def carregar_contexto(session: AsyncSession, conversation_id: str) -> ContextoConversa:
    """Últimas mensagens do cliente (mais antiga primeiro), resumo e e-mail.
    Conversa que ainda não existe devolve um contexto vazio."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        return ContextoConversa()
    resultado = await session.execute(
        select(ConversaMensagem.texto)
        .where(
            ConversaMensagem.conversa_id == conversation_id,
            ConversaMensagem.papel == PAPEL_CLIENTE,
        )
        .order_by(ConversaMensagem.id.desc())
        .limit(MENSAGENS_RECENTES)
    )
    recentes = list(reversed(resultado.scalars().all()))
    return ContextoConversa(
        mensagens_recentes=recentes, resumo=conversa.resumo, email=conversa.email
    )


async def registrar_troca(
    session: AsyncSession,
    conversation_id: str,
    mensagem_cliente: str,
    resposta: str,
    dominio: str | None,
) -> Conversa:
    """Grava a mensagem do cliente e a resposta do assistente (criando a
    conversa na primeira troca) e devolve a conversa atualizada."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        conversa = Conversa(id=conversation_id, mensagens_resumidas=0)
        session.add(conversa)
    session.add_all(
        [
            ConversaMensagem(
                conversa_id=conversation_id,
                papel=PAPEL_CLIENTE,
                texto=mensagem_cliente[:_TEXTO_MAX_CHARS],
            ),
            ConversaMensagem(
                conversa_id=conversation_id,
                papel=PAPEL_ASSISTENTE,
                texto=resposta[:_TEXTO_MAX_CHARS],
                dominio=dominio,
            ),
        ]
    )
    # `onupdate` do `atualizada_em` só dispara quando alguma coluna da
    # conversa muda; numa troca sem mudança nela, atualiza à mão.
    conversa.atualizada_em = func.now()
    await session.commit()
    await session.refresh(conversa)
    return conversa


async def contar_mensagens(session: AsyncSession, conversation_id: str) -> int:
    resultado = await session.execute(
        select(func.count())
        .select_from(ConversaMensagem)
        .where(ConversaMensagem.conversa_id == conversation_id)
    )
    return resultado.scalar_one()


async def listar_mensagens(
    session: AsyncSession, conversation_id: str, limite: int = 50
) -> list[ConversaMensagem]:
    """As últimas `limite` mensagens da conversa, mais antiga primeiro —
    para o widget reexibir o histórico ao reabrir o chat."""
    resultado = await session.execute(
        select(ConversaMensagem)
        .where(ConversaMensagem.conversa_id == conversation_id)
        .order_by(ConversaMensagem.id.desc())
        .limit(limite)
    )
    return list(reversed(resultado.scalars().all()))
