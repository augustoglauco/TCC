"""Classificação do usuário como Cliente, Esporádico ou Lead (R10, Fase 6) —
ver decisão de 2026-09-25 em docs/ARCHITECTURE.md §5.

A identidade é o e-mail, captado no momento natural da conversa (o visitante
o escreve no pós-venda, quando o assistente pede, ou no agendamento) e
cruzado com a base de clientes fictícia (`clientes`/`cliente_compras`).

# MVP: e-mail captado por expressão regular, sem confirmação de posse;
# regras fixas (quantidade e recência das compras, intenção de compra pelo
# domínio das respostas), sem modelo preditivo.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Cliente, ClienteCompra, Conversa, ConversaMensagem
from app.memory.store import PAPEL_ASSISTENTE

PERFIL_CLIENTE = "cliente"
PERFIL_ESPORADICO = "esporadico"
PERFIL_LEAD = "lead"
PERFIL_NAO_CLASSIFICADO = "nao_classificado"

# Cliente = 2 ou mais compras, a última dentro desta janela.
JANELA_RECENCIA = timedelta(days=365)
# Domínios de resposta que indicam intenção de compra.
DOMINIOS_INTENCAO_COMPRA = frozenset({"vendas", "agendamento"})
# Domínios de pós-venda: sem e-mail conhecido, o assistente pede o da compra.
DOMINIOS_POS_VENDA = frozenset({"suporte", "atendimento"})

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")


@dataclass
class Classificacao:
    perfil: str
    motivo: str


def extrair_email(texto: str) -> str | None:
    """Primeiro e-mail do texto, em minúsculas (o cadastro compara assim)."""
    encontrado = _EMAIL_RE.search(texto)
    return encontrado.group(0).lower() if encontrado else None


# Palavras que podem acompanhar um e-mail numa mensagem que só o informa
# ("Sou fulano@…", "meu e-mail é …", "segue meu email: …").
_PALAVRAS_SO_EMAIL = frozenset(
    {
        "sou", "o", "a", "meu", "minha", "e", "mail", "email", "é", "eh", "e-mail",
        "segue", "aqui", "está", "esta", "ai", "aí", "oi", "olá", "ola", "bom",
        "boa", "dia", "tarde", "noite", "obrigado", "obrigada", "de", "do",
        "contato", "cadastro", "pode", "anotar",
    }
)  # fmt: skip

RESPOSTA_SO_EMAIL = (
    "Obrigado! Anotei o seu e-mail — isso facilita o nosso atendimento e o "
    "relacionamento com você. Em que posso ajudar?"
)


def e_mensagem_so_de_email(texto: str) -> bool:
    """`True` quando a mensagem é basicamente só um e-mail — respondida sem
    LLM (resposta fixa). Com uma pergunta junto ("meu e-mail é X, quanto
    custa o GD-15?"), segue o fluxo normal do roteador."""
    email = extrair_email(texto)
    if email is None:
        return False
    resto = _EMAIL_RE.sub(" ", texto.lower())
    palavras = re.findall(r"[\wà-ú-]+", resto)
    return len(palavras) <= 8 and all(p in _PALAVRAS_SO_EMAIL for p in palavras)


def classificar(
    datas_compras: list[datetime] | None,
    tem_email: bool,
    teve_intencao_compra: bool,
    agora: datetime,
) -> Classificacao:
    """Regra pura. `datas_compras` é `None` quando o e-mail não está na base
    (ou não há e-mail); lista (possivelmente vazia) quando está."""
    if datas_compras:
        ultima = max(datas_compras)
        recente = agora - ultima <= JANELA_RECENCIA
        if len(datas_compras) >= 2 and recente:
            return Classificacao(
                PERFIL_CLIENTE,
                f"{len(datas_compras)} compras, a última há {(agora - ultima).days} dias",
            )
        if len(datas_compras) == 1:
            return Classificacao(PERFIL_ESPORADICO, "cadastrado, com uma única compra")
        return Classificacao(
            PERFIL_ESPORADICO,
            f"{len(datas_compras)} compras, a última há {(agora - ultima).days} dias",
        )
    if teve_intencao_compra:
        motivo = "intenção de compra, e-mail sem cadastro" if tem_email else "intenção de compra"
        return Classificacao(PERFIL_LEAD, motivo)
    if datas_compras is not None:
        # Cadastrado, mas sem nenhuma compra registrada.
        return Classificacao(PERFIL_NAO_CLASSIFICADO, "cadastrado, sem compras")
    return Classificacao(PERFIL_NAO_CLASSIFICADO, "sem sinais ainda")


async def atualizar_perfil(
    session: AsyncSession,
    conversation_id: str,
    mensagem_cliente: str,
    agora: datetime | None = None,
) -> Classificacao | None:
    """Capta o e-mail da mensagem (se houver), recalcula e grava o perfil da
    conversa. Chamado logo depois de gravar a troca, na mesma sessão."""
    conversa = await session.get(Conversa, conversation_id)
    if conversa is None:
        return None
    email = extrair_email(mensagem_cliente)
    if email:
        conversa.email = email

    datas_compras = None
    if conversa.email:
        cliente_id = await session.scalar(select(Cliente.id).where(Cliente.email == conversa.email))
        if cliente_id is not None:
            resultado = await session.execute(
                select(ClienteCompra.comprado_em).where(ClienteCompra.cliente_id == cliente_id)
            )
            datas_compras = [_com_fuso(data) for data in resultado.scalars().all()]

    intencao = await session.scalar(
        select(ConversaMensagem.id)
        .where(
            ConversaMensagem.conversa_id == conversation_id,
            ConversaMensagem.papel == PAPEL_ASSISTENTE,
            ConversaMensagem.dominio.in_(DOMINIOS_INTENCAO_COMPRA),
        )
        .limit(1)
    )
    classificacao = classificar(
        datas_compras, bool(conversa.email), intencao is not None, agora or datetime.now(UTC)
    )
    conversa.perfil = classificacao.perfil
    conversa.perfil_motivo = classificacao.motivo
    await session.commit()
    return classificacao


def _com_fuso(data: datetime) -> datetime:
    # O SQLite dos testes devolve datas sem fuso; o Postgres, com.
    return data if data.tzinfo else data.replace(tzinfo=UTC)
