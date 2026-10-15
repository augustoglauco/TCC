"""Agente autônomo de previsão de estoque (R13, docs/ARCHITECTURE.md,
decisões de 2026-10-15).

A cada venda/reserva (`app.db.catalog.criar_pedido`), para cada produto do
pedido, um de dois "cérebros" (escolhido em `app.agents.runtime`, config
persistente no painel de configurações) decide se avisa o administrador:

- `deterministico`: estoque atual / taxa de baixa diária (média de 30 dias);
  cobertura < horizonte (10 dias) => alerta.
- `ia`: um LLM (local ou externo) recebe os fatos estruturados — estoque por
  centro, consumo diário, tendência, preço — e devolve risco, dias até a
  falta, reposição sugerida e justificativa (`app.agents.estoque_ia`). Se o
  LLM falhar ou devolver lixo, cai na regra determinística.

Os dois publicam pela mesma via (`mensagens_agentes` + e-mail), com o campo
`agente` dizendo quem decidiu (`estoque_preditivo` x `estoque_ia`).

# MVP: taxa constante (média móvel) no modo determinístico; estoque somado
# entre centros; sem reposição automática; no máximo 1 alerta por produto a
# cada 24h (`chave_dedupe`, compartilhada entre os dois modos).
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.email import enviar_email_admin
from app.agents.runtime import runtime
from app.config import Settings, get_settings
from app.db.models import MensagemAgente, Pedido, PedidoItem, Produto, ProdutoEstoque

logger = logging.getLogger("assistente.agents.estoque")

AGENTE_DETERMINISTICO = "estoque_preditivo"
AGENTE_IA = "estoque_ia"
TIPO = "previsao_falta_estoque"
_DEDUPE_HORAS = 24


@dataclass
class FatosEstoque:
    produto_id: int
    nome: str
    categoria: str
    preco: Decimal
    estoque_por_centro: dict[str, int]
    estoque_total: int
    janela_dias: int
    unidades_janela: int
    consumo_diario: list[int]  # do mais antigo ao mais recente, len == janela_dias
    horizonte_dias: int

    @property
    def taxa_diaria(self) -> Decimal:
        return Decimal(self.unidades_janela) / Decimal(self.janela_dias)

    @property
    def cobertura(self) -> Decimal | None:
        return cobertura_dias(self.estoque_total, self.unidades_janela, self.janela_dias)


@dataclass
class Decisao:
    alertar: bool
    agente: str
    severidade: str
    titulo: str
    corpo: str
    dados: dict


def cobertura_dias(estoque: int, unidades_janela: int, janela_dias: int) -> Decimal | None:
    """Dias de cobertura, ou `None` se não há baixa na janela (sem previsão)."""
    if unidades_janela <= 0:
        return None
    taxa = Decimal(unidades_janela) / Decimal(janela_dias)
    return Decimal(estoque) / taxa


async def coletar_fatos(
    session: AsyncSession, produto: Produto, settings: Settings
) -> FatosEstoque:
    janela = settings.estoque_janela_consumo_dias
    estoques = (
        await session.scalars(select(ProdutoEstoque).where(ProdutoEstoque.produto_id == produto.id))
    ).all()
    por_centro = {e.centro_distribuicao: int(e.quantidade) for e in estoques}

    agora = datetime.now(UTC)
    inicio = (agora - timedelta(days=janela - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    linhas = (
        await session.execute(
            select(Pedido.criado_em, PedidoItem.quantidade)
            .join(Pedido, Pedido.id == PedidoItem.pedido_id)
            .where(PedidoItem.produto_id == produto.id, Pedido.criado_em >= inicio)
        )
    ).all()
    diario = [0] * janela
    for criado_em, quantidade in linhas:
        if criado_em.tzinfo is None:
            criado_em = criado_em.replace(tzinfo=UTC)
        idx = (criado_em.date() - inicio.date()).days
        if 0 <= idx < janela:
            diario[idx] += int(quantidade)
    return FatosEstoque(
        produto_id=produto.id,
        nome=produto.nome,
        categoria=produto.categoria,
        preco=produto.preco,
        estoque_por_centro=por_centro,
        estoque_total=sum(por_centro.values()),
        janela_dias=janela,
        unidades_janela=sum(diario),
        consumo_diario=diario,
        # Horizonte por produto (prazo de reposição próprio); sem valor, o padrão global.
        horizonte_dias=produto.dias_alerta_estoque or settings.estoque_horizonte_dias,
    )


def decidir_deterministico(f: FatosEstoque) -> Decisao:
    cobertura = f.cobertura
    if cobertura is None or cobertura >= f.horizonte_dias:
        return Decisao(False, AGENTE_DETERMINISTICO, "aviso", "", "", {})
    dias = max(int(cobertura), 0)
    titulo = f"Risco de falta: {f.nome} (~{dias} dias de estoque)"
    corpo = (
        f'O produto "{f.nome}" (id {f.produto_id}) tem {f.estoque_total} unidade(s) em '
        f"estoque e baixa média de {f.taxa_diaria:.2f} unidade(s)/dia nos últimos "
        f"{f.janela_dias} dias ({f.unidades_janela} reservadas/vendidas). Nesse ritmo o "
        f"estoque acaba em cerca de {dias} dia(s), abaixo do horizonte de "
        f"{f.horizonte_dias} dias. Considere repor."
    )
    return Decisao(
        True,
        AGENTE_DETERMINISTICO,
        "critico" if dias <= 3 else "aviso",
        titulo,
        corpo,
        {
            "produto_id": f.produto_id,
            "metodo": "deterministico",
            "estoque_atual": f.estoque_total,
            "taxa_diaria": float(round(f.taxa_diaria, 3)),
            "cobertura_dias": float(round(cobertura, 1)),
            "horizonte_dias": f.horizonte_dias,
        },
    )


async def _ja_alertado(session: AsyncSession, chave: str) -> bool:
    desde = datetime.now(UTC) - timedelta(hours=_DEDUPE_HORAS)
    existe = await session.scalar(
        select(MensagemAgente.id)
        .where(MensagemAgente.chave_dedupe == chave, MensagemAgente.criado_em >= desde)
        .limit(1)
    )
    return existe is not None


async def _decidir(f: FatosEstoque, settings: Settings) -> Decisao:
    if runtime.estoque_modo == "ia":
        from app.agents.estoque_ia import decidir_com_ia

        decisao = await decidir_com_ia(f, runtime.llm_client(), runtime.estoque_llm)
        if decisao is not None:
            return decisao
        logger.warning("Agente de estoque (IA) sem resposta válida; usando a regra determinística")
    return decidir_deterministico(f)


async def avaliar_estoque(
    session: AsyncSession,
    produto_ids: Iterable[int],
    *,
    settings: Settings | None = None,
) -> list[MensagemAgente]:
    """Avalia os produtos e devolve as mensagens criadas (já commitadas)."""
    if runtime.estoque_modo == "desativado":
        return []
    settings = settings or get_settings()
    criadas: list[MensagemAgente] = []

    for produto_id in sorted(set(produto_ids)):
        produto = await session.get(Produto, produto_id)
        if produto is None:
            continue
        chave = f"estoque:{produto_id}"
        fatos = await coletar_fatos(session, produto, settings)
        # Sem baixa na janela não há o que prever (nem custo de LLM a gastar).
        if fatos.unidades_janela <= 0:
            continue
        if await _ja_alertado(session, chave):
            continue

        decisao = await _decidir(fatos, settings)
        if not decisao.alertar:
            continue

        mensagem = MensagemAgente(
            agente=decisao.agente,
            tipo=TIPO,
            severidade=decisao.severidade,
            titulo=decisao.titulo,
            corpo=decisao.corpo,
            dados=decisao.dados,
            chave_dedupe=chave,
        )
        mensagem.email_status = await enviar_email_admin(settings, decisao.titulo, decisao.corpo)
        session.add(mensagem)
        await session.commit()
        criadas.append(mensagem)
        logger.info("Alerta de estoque (%s) criado para o produto %s", decisao.agente, produto_id)

    return criadas


async def avaliar_estoque_em_segundo_plano(produto_ids: set[int]) -> None:
    """Variante com sessão própria, para o modo IA (o LLM leva segundos e a
    reserva não pode esperar por ele)."""
    from app.services.ai_usage import _global_sessionmaker

    if _global_sessionmaker is None:
        return
    try:
        async with _global_sessionmaker() as session:
            await avaliar_estoque(session, produto_ids)
    except Exception:  # noqa: BLE001
        logger.exception("Agente de estoque (segundo plano) falhou")
