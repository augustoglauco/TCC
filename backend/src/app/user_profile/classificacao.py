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
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Cliente, ClienteCompra, Conversa, ConversaMensagem, Pedido, Produto
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


async def carregar_contexto_cliente(
    session: AsyncSession,
    email: str,
    apenas_tipo_cliente: bool = False,
) -> str | None:
    """Carrega dados cadastrais, perfil e histórico de compras/pedidos do cliente
    para enriquecer o prompt do assistente (R10, Fase 6/7).
    Quando apenas_tipo_cliente=True (usuário não autenticado no chat), expõe apenas a
    classificação de tipo de cliente no chat sem compras, pedidos ou dados pessoais.
    """
    if not email:
        return None

    email_clean = email.strip().lower()
    cliente = await session.scalar(select(Cliente).where(Cliente.email == email_clean))

    # Compras históricas (tabela cliente_compras semeada na migração 0011)
    rows_compras: list[tuple[ClienteCompra, str | None]] = []
    if cliente is not None:
        stmt_compras = (
            select(ClienteCompra, Produto.nome)
            .outerjoin(Produto, ClienteCompra.produto_id == Produto.id)
            .where(ClienteCompra.cliente_id == cliente.id)
            .order_by(ClienteCompra.comprado_em.desc())
        )
        res_compras = await session.execute(stmt_compras)
        rows_compras = list(res_compras.all())

    # Pedidos da plataforma/chat (tabela pedidos)
    stmt_pedidos = (
        select(Pedido)
        .options(selectinload(Pedido.itens))
        .where(Pedido.user_email == email_clean)
        .order_by(Pedido.criado_em.desc())
    )
    pedidos_res = await session.execute(stmt_pedidos)
    pedidos_usuario = list(pedidos_res.scalars().all())

    if cliente is None and not pedidos_usuario:
        return None

    datas_compras = [_com_fuso(compra.comprado_em) for compra, _ in rows_compras] + [
        _com_fuso(pedido.criado_em) for pedido in pedidos_usuario
    ]

    agora = datetime.now(UTC)
    classificacao = classificar(
        datas_compras=datas_compras if (cliente or pedidos_usuario) else None,
        tem_email=True,
        teve_intencao_compra=False,
        agora=agora,
    )

    if apenas_tipo_cliente:
        return "\n".join(
            [
                "[Perfil do Visitante no Chat (Não Autenticado)]:",
                f"- Tipo de cliente: {classificacao.perfil} ({classificacao.motivo})",
                "- Status de autenticação: NÃO AUTENTICADO (visitante anônimo no chat).",
                "- Regra de segurança e privacidade: O visitante NÃO está autenticado na conta. "
                "Por proteção de dados, NUNCA revele compras anteriores, pedidos, valores ou "
                "dados pessoais. Se o visitante perguntar sobre compras feitas, histórico de "
                "pedidos ou dados da conta, instrua-o educadamente a entrar na conta (fazer "
                "login) para acessar suas informações.",
            ]
        )

    nome_cliente = cliente.nome if cliente else email_clean.split("@")[0].title()

    linhas = [
        "[Dados do Cliente e Histórico de Compras]:",
        f"- Nome do cliente: {nome_cliente}",
        f"- E-mail do cliente: {email_clean}",
        f"- Perfil de relacionamento: {classificacao.perfil} ({classificacao.motivo})",
    ]

    tem_compras = bool(rows_compras or pedidos_usuario)
    if tem_compras:
        linhas.append("- Histórico de Compras e Pedidos Realizados:")
        for compra, nome_prod in rows_compras:
            data_str = _com_fuso(compra.comprado_em).strftime("%d/%m/%Y")
            prod_str = nome_prod or f"Produto #{compra.produto_id}"
            valor_fmt = (
                f"R$ {compra.valor_total:,.2f}".replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
            linhas.append(
                f"  * {compra.quantidade}x {prod_str} ({valor_fmt}) comprado em {data_str}"
            )

        for pedido in pedidos_usuario:
            data_str = _com_fuso(pedido.criado_em).strftime("%d/%m/%Y")
            total_pedido = sum(
                Decimal(str(it.preco_unitario)) * it.quantidade for it in pedido.itens
            )
            valor_fmt = (
                f"R$ {total_pedido:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            itens_desc = []
            for it in pedido.itens:
                prod = await session.get(Produto, it.produto_id)
                prod_nome = prod.nome if prod else f"Produto #{it.produto_id}"
                itens_desc.append(f"{it.quantidade}x {prod_nome}")
            resumo_itens = ", ".join(itens_desc) if itens_desc else "itens do pedido"
            linhas.append(
                f"  * Pedido #{str(pedido.id)[:8]} (Status: {pedido.status}) - "
                f"{resumo_itens} ({valor_fmt}) em {data_str}"
            )
    else:
        linhas.append(
            "- Histórico: Nenhuma compra anterior registrada no sistema para este e-mail."
        )

    return "\n".join(linhas)
