"""Agente autônomo de previsão de estoque (R13, docs/ARCHITECTURE.md,
decisão de 2026-10-15).

A cada venda/reserva (`app.db.catalog.criar_pedido`), para cada produto do
pedido: estoque atual (soma dos centros) / taxa de baixa diária (unidades
reservadas na janela / dias da janela). Cobertura menor que o horizonte
(10 dias) => mensagem para o administrador (página + e-mail).

# MVP: taxa constante (média móvel), sem sazonalidade; estoque somado entre
# centros; sem reposição automática; no máximo 1 alerta por produto a cada
# 24h (`chave_dedupe`).
"""

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email import enviar_email_admin
from app.config import Settings, get_settings
from app.db.models import MensagemAgente, Pedido, PedidoItem, Produto, ProdutoEstoque

logger = logging.getLogger("assistente.agents.estoque")

AGENTE = "estoque_preditivo"
TIPO = "previsao_falta_estoque"
_DEDUPE_HORAS = 24


async def _estoque_atual(session: AsyncSession, produto_id: int) -> int:
    total = await session.scalar(
        select(func.coalesce(func.sum(ProdutoEstoque.quantidade), 0)).where(
            ProdutoEstoque.produto_id == produto_id
        )
    )
    return int(total or 0)


async def _unidades_na_janela(session: AsyncSession, produto_id: int, dias: int) -> int:
    desde = datetime.now(UTC) - timedelta(days=dias)
    total = await session.scalar(
        select(func.coalesce(func.sum(PedidoItem.quantidade), 0))
        .join(Pedido, Pedido.id == PedidoItem.pedido_id)
        .where(PedidoItem.produto_id == produto_id, Pedido.criado_em >= desde)
    )
    return int(total or 0)


def cobertura_dias(estoque: int, unidades_janela: int, janela_dias: int) -> Decimal | None:
    """Dias de cobertura, ou `None` se não há baixa na janela (sem previsão)."""
    if unidades_janela <= 0:
        return None
    taxa = Decimal(unidades_janela) / Decimal(janela_dias)
    return Decimal(estoque) / taxa


async def _ja_alertado(session: AsyncSession, chave: str) -> bool:
    desde = datetime.now(UTC) - timedelta(hours=_DEDUPE_HORAS)
    existe = await session.scalar(
        select(MensagemAgente.id)
        .where(MensagemAgente.chave_dedupe == chave, MensagemAgente.criado_em >= desde)
        .limit(1)
    )
    return existe is not None


async def avaliar_estoque(
    session: AsyncSession,
    produto_ids: Iterable[int],
    *,
    settings: Settings | None = None,
) -> list[MensagemAgente]:
    """Avalia os produtos e devolve as mensagens criadas (já commitadas)."""
    settings = settings or get_settings()
    horizonte = settings.estoque_horizonte_dias
    janela = settings.estoque_janela_consumo_dias
    criadas: list[MensagemAgente] = []

    for produto_id in sorted(set(produto_ids)):
        produto = await session.get(Produto, produto_id)
        if produto is None:
            continue
        estoque = await _estoque_atual(session, produto_id)
        unidades = await _unidades_na_janela(session, produto_id, janela)
        cobertura = cobertura_dias(estoque, unidades, janela)
        if cobertura is None or cobertura >= horizonte:
            continue

        chave = f"{AGENTE}:{produto_id}"
        if await _ja_alertado(session, chave):
            continue

        taxa = Decimal(unidades) / Decimal(janela)
        dias = max(int(cobertura), 0)
        titulo = f"Risco de falta: {produto.nome} (~{dias} dias de estoque)"
        corpo = (
            f'O produto "{produto.nome}" (id {produto_id}) tem {estoque} unidade(s) em '
            f"estoque e baixa média de {taxa:.2f} unidade(s)/dia nos últimos {janela} dias "
            f"({unidades} reservadas/vendidas). Nesse ritmo o estoque acaba em cerca de "
            f"{dias} dia(s), abaixo do horizonte de {horizonte} dias. Considere repor."
        )
        mensagem = MensagemAgente(
            agente=AGENTE,
            tipo=TIPO,
            severidade="critico" if dias <= 3 else "aviso",
            titulo=titulo,
            corpo=corpo,
            dados={
                "produto_id": produto_id,
                "estoque_atual": estoque,
                "taxa_diaria": float(round(taxa, 3)),
                "cobertura_dias": float(round(cobertura, 1)),
                "horizonte_dias": horizonte,
            },
            chave_dedupe=chave,
        )
        mensagem.email_status = await enviar_email_admin(settings, titulo, corpo)
        session.add(mensagem)
        await session.commit()
        criadas.append(mensagem)
        logger.info("Alerta de estoque criado para o produto %s", produto_id)

    return criadas
