from datetime import datetime, UTC
from typing import Any
import logging
from sqlalchemy import select, update, desc, asc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Conversa, ConversaMensagem

logger = logging.getLogger(__name__)


async def escalar_para_humano(
    session: AsyncSession,
    conversation_id: str,
    motivo: str = "tom_frustrado",
    prioridade: int = 5,
) -> Conversa:
    """Escala uma conversa para a fila de atendimento humano."""
    now = datetime.now(UTC)
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        conversa = Conversa(
            id=conversation_id,
            status="aguardando_humano",
            motivo_escalonamento=motivo,
            prioridade=prioridade,
            escalado_em=now,
        )
        session.add(conversa)
    else:
        conversa.status = "aguardando_humano"
        conversa.motivo_escalonamento = motivo
        conversa.prioridade = prioridade
        conversa.escalado_em = now

    await session.commit()
    await session.refresh(conversa)
    logger.info(
        "conversa_escalada_humano",
        extra={
            "router": {
                "event": "conversa_escalada_humano",
                "conversation_id": conversation_id,
                "motivo": motivo,
                "prioridade": prioridade,
            }
        },
    )
    return conversa


async def listar_fila_espera(session: AsyncSession) -> list[dict[str, Any]]:
    """Lista todas as conversas aguardando atendimento humano, ordenadas por prioridade desc e tempo asc."""
    stmt = (
        select(Conversa)
        .options(selectinload(Conversa.mensagens))
        .where(Conversa.status == "aguardando_humano")
        .order_by(desc(Conversa.prioridade), asc(Conversa.escalado_em))
    )
    result = await session.execute(stmt)
    conversas = result.scalars().all()

    fila: list[dict[str, Any]] = []
    for c in conversas:
        ultimas_mensagens = c.mensagens or []
        ultima_msg_cliente = None
        for m in reversed(ultimas_mensagens):
            if m.papel == "cliente":
                ultima_msg_cliente = m.texto
                break

        fila.append({
            "id": c.id,
            "status": c.status,
            "motivo_escalonamento": c.motivo_escalonamento,
            "prioridade": c.prioridade,
            "escalado_em": c.escalado_em.isoformat() if c.escalado_em else None,
            "email": c.email,
            "perfil": c.perfil,
            "total_mensagens": len(ultimas_mensagens),
            "ultima_mensagem": ultima_msg_cliente,
        })
    return fila


async def listar_meus_chats(session: AsyncSession, atendente_id: str) -> list[dict[str, Any]]:
    """Lista as conversas ativas assumidas pelo atendente especificado."""
    stmt = (
        select(Conversa)
        .options(selectinload(Conversa.mensagens))
        .where(
            Conversa.status == "em_atendimento_humano",
            Conversa.atendente_id == atendente_id,
        )
        .order_by(desc(Conversa.atualizada_em))
    )
    result = await session.execute(stmt)
    conversas = result.scalars().all()

    chats: list[dict[str, Any]] = []
    for c in conversas:
        ultimas_mensagens = c.mensagens or []
        ultima_msg_cliente = None
        for m in reversed(ultimas_mensagens):
            if m.papel == "cliente":
                ultima_msg_cliente = m.texto
                break

        chats.append({
            "id": c.id,
            "status": c.status,
            "atendente_id": c.atendente_id,
            "atendente_nome": c.atendente_nome,
            "motivo_escalonamento": c.motivo_escalonamento,
            "prioridade": c.prioridade,
            "escalado_em": c.escalado_em.isoformat() if c.escalado_em else None,
            "email": c.email,
            "perfil": c.perfil,
            "total_mensagens": len(ultimas_mensagens),
            "ultima_mensagem": ultima_msg_cliente,
        })
    return chats


async def obter_detalhes_atendimento(session: AsyncSession, conversation_id: str) -> dict[str, Any] | None:
    """Retorna o histórico completo e contexto da conversa para o operador humano."""
    stmt = (
        select(Conversa)
        .options(selectinload(Conversa.mensagens))
        .where(Conversa.id == conversation_id)
    )
    result = await session.execute(stmt)
    conversa = result.scalar_one_or_none()
    if conversa is None:
        return None

    mensagens_list = []
    for m in conversa.mensagens or []:
        mensagens_list.append({
            "id": m.id,
            "papel": m.papel,
            "atendente_nome": m.atendente_nome,
            "texto": m.texto,
            "dominio": m.dominio,
            "metricas": m.metricas,
            "criada_em": m.criada_em.isoformat() if m.criada_em else None,
        })

    return {
        "id": conversa.id,
        "status": conversa.status,
        "atendente_id": conversa.atendente_id,
        "atendente_nome": conversa.atendente_nome,
        "motivo_escalonamento": conversa.motivo_escalonamento,
        "prioridade": conversa.prioridade,
        "escalado_em": conversa.escalado_em.isoformat() if conversa.escalado_em else None,
        "email": conversa.email,
        "perfil": conversa.perfil,
        "resumo": conversa.resumo,
        "mensagens": mensagens_list,
    }


async def claim_conversa(
    session: AsyncSession,
    conversation_id: str,
    atendente_id: str,
    atendente_nome: str,
) -> bool:
    """Realiza o claim atômico de uma conversa da fila de espera.
    
    Garante que se dois operadores clicarem ao mesmo tempo, exatamente um
    consegue assumir (retorna True) e o outro falha (retorna False, 0 rows).
    """
    stmt = (
        update(Conversa)
        .where(
            Conversa.id == conversation_id,
            Conversa.status == "aguardando_humano",
            Conversa.atendente_id.is_(None),
        )
        .values(
            status="em_atendimento_humano",
            atendente_id=atendente_id,
            atendente_nome=atendente_nome,
            atualizada_em=datetime.now(UTC),
        )
    )
    res = await session.execute(stmt)
    await session.commit()
    session.expire_all()
    return res.rowcount > 0


async def enviar_mensagem_atendente(
    session: AsyncSession,
    conversation_id: str,
    atendente_nome: str,
    texto: str,
) -> ConversaMensagem:
    """Grava mensagem enviada pelo atendente humano na conversa."""
    msg = ConversaMensagem(
        conversa_id=conversation_id,
        papel="atendente",
        atendente_nome=atendente_nome,
        texto=texto,
    )
    session.add(msg)
    # Atualiza atualizada_em da conversa
    await session.execute(
        update(Conversa)
        .where(Conversa.id == conversation_id)
        .values(atualizada_em=datetime.now(UTC))
    )
    await session.commit()
    await session.refresh(msg)
    return msg


async def finalizar_atendimento(
    session: AsyncSession,
    conversation_id: str,
    motivo: str = "atendimento_humano_concluido",
) -> Conversa:
    """Encerra formalmente o atendimento da conversa."""
    now = datetime.now(UTC)
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        raise ValueError(f"Conversa {conversation_id} não encontrada.")

    conversa.status = "encerrada"
    conversa.encerrada_em = now
    conversa.motivo_encerramento = motivo
    await session.commit()
    await session.refresh(conversa)
    return conversa


async def devolver_para_ia(
    session: AsyncSession,
    conversation_id: str,
) -> Conversa:
    """Devolve a conversa para a IA continuar o atendimento de forma automática."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        raise ValueError(f"Conversa {conversation_id} não encontrada.")

    conversa.status = "aberta"
    conversa.atendente_id = None
    conversa.atendente_nome = None
    conversa.motivo_escalonamento = None
    await session.commit()
    await session.refresh(conversa)
    return conversa
