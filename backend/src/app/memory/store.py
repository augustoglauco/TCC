"""Memória da conversa no Postgres (R9, Fase 6) — ver decisão de 2026-09-25
em docs/ARCHITECTURE.md §5.

Substitui o histórico em memória de `app.api.chat`: cada troca (mensagem do
cliente + resposta do assistente) é gravada em `conversa_mensagens`, e o
histórico recente usado pelo roteador passa a vir daqui.

# MVP: um visitante = um navegador (conversation_id no localStorage), sem
# login; texto guardado sem política de retenção (ver §7 da arquitetura).
"""

from dataclasses import dataclass, field

from sqlalchemy import delete, func, select
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
    # (mensagem do cliente, resposta do assistente) da troca anterior — dá
    # contexto a "o produto acima", "e esse?" (correção de 2026-09-27).
    ultima_troca: tuple[str, str] | None = None


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
    ultimas = (
        (
            await session.execute(
                select(ConversaMensagem)
                .where(ConversaMensagem.conversa_id == conversation_id)
                .order_by(ConversaMensagem.id.desc())
                .limit(2)
            )
        )
        .scalars()
        .all()
    )
    ultima_troca = None
    if (
        len(ultimas) == 2
        and ultimas[0].papel == PAPEL_ASSISTENTE
        and ultimas[1].papel == PAPEL_CLIENTE
    ):
        ultima_troca = (ultimas[1].texto, ultimas[0].texto)
    return ContextoConversa(
        mensagens_recentes=recentes,
        resumo=conversa.resumo,
        email=conversa.email,
        ultima_troca=ultima_troca,
    )


async def registrar_troca(
    session: AsyncSession,
    conversation_id: str,
    mensagem_cliente: str,
    resposta: str,
    dominio: str | None,
) -> tuple[Conversa, ConversaMensagem]:
    """Grava a mensagem do cliente e a resposta do assistente (criando a
    conversa na primeira troca) e devolve a conversa atualizada e a mensagem
    do assistente (para as métricas, gravadas depois do perfil)."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        conversa = Conversa(id=conversation_id, mensagens_resumidas=0)
        session.add(conversa)
    assistente = ConversaMensagem(
        conversa_id=conversation_id,
        papel=PAPEL_ASSISTENTE,
        texto=resposta[:_TEXTO_MAX_CHARS],
        dominio=dominio,
    )
    session.add_all(
        [
            ConversaMensagem(
                conversa_id=conversation_id,
                papel=PAPEL_CLIENTE,
                texto=mensagem_cliente[:_TEXTO_MAX_CHARS],
            ),
            assistente,
        ]
    )
    # `onupdate` do `atualizada_em` só dispara quando alguma coluna da
    # conversa muda; numa troca sem mudança nela, atualiza à mão.
    conversa.atualizada_em = func.now()
    await session.commit()
    await session.refresh(conversa)
    return conversa, assistente


async def gravar_metricas(
    session: AsyncSession, mensagem: ConversaMensagem, metricas: dict
) -> None:
    """Guarda as métricas do `done` na resposta do assistente (R9)."""
    mensagem.metricas = metricas
    await session.commit()


async def registrar_email(session: AsyncSession, conversation_id: str, email: str) -> None:
    """Guarda o e-mail na conversa (criando-a, se preciso) assim que a
    mensagem chega, antes do LLM: uma falha na resposta não o perde (R10)."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        conversa = Conversa(id=conversation_id, mensagens_resumidas=0)
        session.add(conversa)
    conversa.email = email
    await session.commit()


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


async def limpar_conversa(session: AsyncSession, conversation_id: str) -> bool:
    """Deleta todas as mensagens da conversa e reseta os campos de memória/resumo no Postgres.
    Retorna True se a conversa existia, False caso contrário.

    # MVP: o e-mail da conversa é mantido (a identidade do visitante não é
    # "memória da conversa"); o perfil é recalculado na próxima mensagem.
    """
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        return False
    await session.execute(
        delete(ConversaMensagem).where(ConversaMensagem.conversa_id == conversation_id)
    )
    conversa.resumo = None
    conversa.perfil = None
    conversa.perfil_motivo = None
    conversa.mensagens_resumidas = 0
    await session.commit()
    return True


async def obter_contexto_conversa_anterior(
    session: AsyncSession, email: str, conversa_atual_id: str | None = None
) -> str | None:
    """Recupera o resumo ou histórico condensado da conversa anterior mais recente
    associada ao e-mail do cliente (R9/R10). Ignora a conversa atual.
    Retorna o resumo se houver; caso contrário, formata as mensagens recentes
    daquela conversa; se não houver conversa anterior, retorna None."""
    stmt = select(Conversa).where(Conversa.email == email)
    if conversa_atual_id:
        stmt = stmt.where(Conversa.id != conversa_atual_id)
    stmt = stmt.order_by(Conversa.atualizada_em.desc(), Conversa.criada_em.desc()).limit(1)

    resultado = await session.execute(stmt)
    conversa_anterior = resultado.scalars().first()
    if conversa_anterior is None:
        return None

    if conversa_anterior.resumo:
        return conversa_anterior.resumo.strip()

    mensagens = await listar_mensagens(session, conversa_anterior.id, limite=6)
    if not mensagens:
        return None

    linhas = [
        f"{'Cliente' if m.papel == PAPEL_CLIENTE else 'Assistente'}: {m.texto}"
        for m in mensagens
    ]
    return "\n".join(linhas)
