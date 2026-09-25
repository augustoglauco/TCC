"""Resumo automático periódico da conversa (R9, Fase 6) — ver decisão de
2026-09-25 em docs/ARCHITECTURE.md §5.

A cada `INTERVALO_RESUMO` mensagens novas gravadas, o LLM local reescreve o
resumo a partir do resumo anterior e das mensagens ainda não resumidas.
Roda em segundo plano (disparado por `app.api.chat` depois do `done`), e o
resumo entra no prompt das respostas seguintes.

# MVP: resumo por reescrita simples (resumo anterior + mensagens novas), sem
# limite de tamanho além da instrução no prompt e sem reavaliar a qualidade.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Conversa, ConversaMensagem
from app.memory.store import PAPEL_CLIENTE
from app.router.llm_client import LLMClient

logger = logging.getLogger(__name__)

# 6 mensagens = 3 trocas (cliente + assistente).
INTERVALO_RESUMO = 6

_PROMPT_RESUMO = """\
Você mantém o resumo de uma conversa de atendimento de uma empresa que vende \
geradores e acessórios. Reescreva o resumo incorporando as mensagens novas.

Regras:
- No máximo 5 frases curtas, em português.
- Guarde o que ajuda a continuar o atendimento: produtos citados, \
quantidades, valores informados, datas, dados que o cliente forneceu e o que \
ficou pendente.
- Não invente nada que não esteja no resumo anterior ou nas mensagens.
- Responda só com o texto do resumo, sem título nem comentários.

Resumo anterior:
{resumo_anterior}

Mensagens novas:
{mensagens}"""


def precisa_resumir(total_mensagens: int, mensagens_resumidas: int) -> bool:
    return total_mensagens - mensagens_resumidas >= INTERVALO_RESUMO


async def atualizar_resumo(
    session_factory: async_sessionmaker[AsyncSession],
    conversation_id: str,
    llm_client: LLMClient,
) -> None:
    """Reescreve o resumo com as mensagens ainda não resumidas. Nunca levanta:
    roda em segundo plano, e uma falha só adia o resumo para a próxima
    troca (as mensagens continuam contando como não resumidas)."""
    try:
        async with session_factory() as session:
            conversa = await session.get(Conversa, conversation_id)
            if conversa is None:
                return
            resultado = await session.execute(
                select(ConversaMensagem)
                .where(ConversaMensagem.conversa_id == conversation_id)
                .order_by(ConversaMensagem.id)
                .offset(conversa.mensagens_resumidas)
            )
            novas = list(resultado.scalars().all())
            if len(novas) < INTERVALO_RESUMO:
                return
            prompt = _PROMPT_RESUMO.format(
                resumo_anterior=conversa.resumo or "(nenhum ainda)",
                mensagens="\n".join(
                    f"{'Cliente' if m.papel == PAPEL_CLIENTE else 'Assistente'}: {m.texto}"
                    for m in novas
                ),
            )
            resposta = await llm_client.generate(prompt)
            resumo = resposta.text.strip()
            if not resumo:
                raise ValueError("LLM devolveu resumo vazio")
            conversa.resumo = resumo
            conversa.mensagens_resumidas += len(novas)
            mensagens_resumidas = conversa.mensagens_resumidas
            await session.commit()
        logger.info(
            "resumo_atualizado",
            extra={
                "router": {
                    "event": "resumo_atualizado",
                    "mensagens_resumidas": mensagens_resumidas,
                }
            },
        )
    except Exception as exc:
        logger.warning(
            "resumo_falhou",
            extra={
                "router": {"event": "resumo_falhou", "tipo": type(exc).__name__, "erro": str(exc)}
            },
        )
