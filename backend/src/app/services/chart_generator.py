"""Serviço de geração e agregação analítica de gráficos dinâmicos para Administradores.

Executa consultas analíticas pré-compiladas e seguras (SQLAlchemy) e persiste
definições e dados na tabela `admin_charts`.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AdminChart,
    ClienteCompra,
    ConversaMensagem,
    Pedido,
    PedidoItem,
    Produto,
    ProdutoEstoque,
)

logger = logging.getLogger("assistente.chart_generator")

SUPPORTED_QUERIES = {
    "vendas_produtos_quantidade": "Quantidade de unidades vendidas por produto",
    "vendas_produtos_valor": "Faturamento e valor vendido por produto",
    "vendas_por_categoria": "Distribuição de produtos e valor por categoria",
    "vendas_categoria_quantidade": "Quantidade de itens por categoria",
    "estoque_por_cd": "Quantidade de estoque por centro de distribuição",
    "pedidos_por_status": "Volume de pedidos agrupados por status",
    "metricas_tokens_por_dia": "Consumo de tokens e custos ao longo dos dias",
}


def detect_chart_request(prompt: str) -> dict[str, str] | None:
    """Identifica se o prompt do usuário expressa a intenção explícita de gerar ou
    visualizar um gráfico/dashboard.
    """
    if not prompt or len(prompt.strip()) < 5:
        return None

    texto = prompt.lower()
    gatilhos_grafico = [
        "gráfico",
        "grafico",
        "gráficos",
        "graficos",
        "dashboard",
        "dashboards",
        "plotar",
        "visualização gráfica",
        "visualizacao grafica",
        "painel de gráficos",
    ]

    tem_gatilho = any(g in texto for g in gatilhos_grafico)
    if not tem_gatilho:
        return None

    # Detecta tipo de gráfico solicitado
    tipo_grafico = "bar"
    if "pizza" in texto or "circular" in texto:
        tipo_grafico = "pie"
    elif "donut" in texto or "rosquinha" in texto:
        tipo_grafico = "donut"
    elif "linha" in texto or "linhas" in texto:
        tipo_grafico = "line"
    elif "área" in texto or "area" in texto:
        tipo_grafico = "area"

    # Detecta dimensões e métricas solicitadas
    tem_quantidade = any(
        q in texto
        for q in [
            "quantidade",
            "quantidades",
            "qtd",
            "unidade",
            "unidades",
            "volume",
            "itens vendidos",
            "unidades vendidas",
            "mais vendido",
            "mais vendidos",
        ]
    )
    tem_valor = any(
        v in texto
        for v in ["valor", "valores", "faturamento", "receita", "reais", "r$", "dinheiro", "preço", "preco"]
    )
    tem_produto = any(
        p in texto
        for p in [
            "produto",
            "produtos",
            "item",
            "itens",
            "mercadoria",
            "mercadorias",
            "mais vendido",
            "mais vendidos",
        ]
    )
    tem_categoria = any(
        c in texto for c in ["categoria", "categorias", "departamento", "departamentos"]
    )

    if any(k in texto for k in ["estoque", "cd", "centro de distribuição", "centros de distribuicao"]):
        query_key = "estoque_por_cd"
        titulo = "Estoque por Centro de Distribuição"
        descricao = "Total de itens armazenados em cada centro de distribuição"
    elif any(k in texto for k in ["pedido", "pedidos", "status", "reserva", "reservas"]):
        query_key = "pedidos_por_status"
        titulo = "Pedidos por Status"
        descricao = "Volume de pedidos e reservas distribuídos por status"
    elif any(k in texto for k in ["token", "tokens", "custo", "custos", "consumo ia", "llm"]):
        query_key = "metricas_tokens_por_dia"
        titulo = "Consumo de Tokens e Custos por Dia"
        descricao = "Histórico diário de consumo de tokens prompt/completion e custos"
    elif tem_produto and not tem_categoria:
        if tem_valor and not tem_quantidade:
            query_key = "vendas_produtos_valor"
            titulo = "Vendas por Produto (Faturamento)"
            descricao = "Faturamento total gerado por produto vendido"
        else:
            query_key = "vendas_produtos_quantidade"
            titulo = "Vendas por Produto (Quantidade)"
            descricao = "Quantidade total de unidades vendidas por produto"
    elif tem_categoria:
        if tem_quantidade and not tem_valor:
            query_key = "vendas_categoria_quantidade"
            titulo = "Quantidade de Itens por Categoria"
            descricao = "Total de unidades e itens cadastrados por categoria"
        else:
            query_key = "vendas_por_categoria"
            titulo = "Produtos e Vendas por Categoria"
            descricao = "Total estimado e quantidade de itens cadastrados por categoria"
    else:
        if tem_quantidade:
            query_key = "vendas_produtos_quantidade"
            titulo = "Vendas por Produto (Quantidade)"
            descricao = "Quantidade total de unidades vendidas por produto"
        else:
            query_key = "vendas_por_categoria"
            titulo = "Produtos e Vendas por Categoria"
            descricao = "Total estimado e faturamento por categoria"

    return {
        "tipo_grafico": tipo_grafico,
        "query_key": query_key,
        "titulo": titulo,
        "descricao": descricao,
    }


async def execute_chart_aggregation(
    session: AsyncSession, query_key: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Executa a agregação analítica correspondente a `query_key` de forma sanitizada
    e retorna `(config_json, dados_json)` prontos para o Recharts.
    """
    if query_key in ("vendas_produtos_quantidade", "vendas_produtos_valor"):
        q1 = select(
            ClienteCompra.produto_id.label("produto_id"),
            ClienteCompra.quantidade.label("quantidade"),
            ClienteCompra.valor_total.label("valor_total"),
        ).where(ClienteCompra.produto_id.is_not(None))

        q2 = select(
            PedidoItem.produto_id.label("produto_id"),
            PedidoItem.quantidade.label("quantidade"),
            (PedidoItem.quantidade * PedidoItem.preco_unitario).label("valor_total"),
        ).where(PedidoItem.produto_id.is_not(None))

        u = union_all(q1, q2).subquery("vendas_unificadas")

        order_col = (
            func.sum(u.c.quantidade).desc()
            if query_key == "vendas_produtos_quantidade"
            else func.sum(u.c.valor_total).desc()
        )

        stmt = (
            select(
                Produto.nome.label("produto"),
                func.sum(u.c.quantidade).label("quantidade"),
                func.sum(u.c.valor_total).label("total"),
            )
            .join(Produto, u.c.produto_id == Produto.id)
            .group_by(Produto.nome)
            .order_by(order_col)
            .limit(15)
        )
        res = await session.execute(stmt)
        dados = []
        for p_nome, qtd, total in res:
            dados.append(
                {
                    "produto": p_nome or "Produto",
                    "quantidade": int(qtd or 0),
                    "total": float(total or 0.0),
                }
            )

        # Se não houver vendas, lista produtos do catálogo com quantidade 0
        if not dados:
            stmt_cat = select(Produto.nome).order_by(Produto.nome.asc()).limit(10)
            res_cat = await session.execute(stmt_cat)
            for (p_nome,) in res_cat:
                dados.append(
                    {
                        "produto": p_nome,
                        "quantidade": 0,
                        "total": 0.0,
                    }
                )

        if query_key == "vendas_produtos_quantidade":
            config = {
                "x_key": "produto",
                "y_keys": ["quantidade"],
                "labels": {
                    "quantidade": "Quantidade Vendida (Unid.)",
                    "total": "Faturamento (R$)",
                },
                "format": "number",
                "palette": ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
            }
        else:
            config = {
                "x_key": "produto",
                "y_keys": ["total"],
                "labels": {
                    "total": "Faturamento Total (R$)",
                    "quantidade": "Quantidade Vendida (Unid.)",
                },
                "format": "currency",
                "palette": ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
            }
        return config, dados

    elif query_key == "vendas_categoria_quantidade":
        stmt = (
            select(
                Produto.categoria,
                func.count(Produto.id).label("total_itens"),
                func.sum(Produto.preco).label("total"),
            )
            .group_by(Produto.categoria)
            .order_by(func.count(Produto.id).desc())
        )
        res = await session.execute(stmt)
        dados = []
        for cat, itens, total in res:
            dados.append(
                {
                    "categoria": cat or "Sem Categoria",
                    "total_itens": int(itens or 0),
                    "total": float(total or 0.0),
                }
            )
        config = {
            "x_key": "categoria",
            "y_keys": ["total_itens"],
            "labels": {"total_itens": "Quantidade de Itens", "total": "Valor Total (R$)"},
            "format": "number",
            "palette": ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
        }
        return config, dados

    elif query_key == "vendas_por_categoria":
        stmt = (
            select(
                Produto.categoria,
                func.count(Produto.id).label("total_itens"),
                func.sum(Produto.preco).label("total"),
            )
            .group_by(Produto.categoria)
            .order_by(func.sum(Produto.preco).desc())
        )
        res = await session.execute(stmt)
        dados = []
        for cat, itens, total in res:
            dados.append(
                {
                    "categoria": cat or "Sem Categoria",
                    "total_itens": int(itens or 0),
                    "total": float(total or 0.0),
                }
            )
        config = {
            "x_key": "categoria",
            "y_keys": ["total"],
            "labels": {"total": "Valor Total (R$)", "total_itens": "Itens Cadastrados"},
            "format": "currency",
            "palette": ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ec4899", "#06b6d4"],
        }
        return config, dados

    elif query_key == "estoque_por_cd":
        stmt = (
            select(
                ProdutoEstoque.centro_distribuicao,
                func.sum(ProdutoEstoque.quantidade).label("quantidade"),
            )
            .group_by(ProdutoEstoque.centro_distribuicao)
            .order_by(func.sum(ProdutoEstoque.quantidade).desc())
        )
        res = await session.execute(stmt)
        dados = []
        for cd, qtd in res:
            dados.append(
                {
                    "centro_distribuicao": cd or "Outros",
                    "quantidade": int(qtd or 0),
                }
            )
        config = {
            "x_key": "centro_distribuicao",
            "y_keys": ["quantidade"],
            "labels": {"quantidade": "Quantidade em Estoque"},
            "format": "number",
            "palette": ["#10b981", "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6"],
        }
        return config, dados

    elif query_key == "pedidos_por_status":
        stmt = (
            select(
                Pedido.status,
                func.count(Pedido.id).label("total"),
            )
            .group_by(Pedido.status)
            .order_by(func.count(Pedido.id).desc())
        )
        res = await session.execute(stmt)
        dados = []
        for st, total in res:
            dados.append(
                {
                    "status": (st or "desconhecido").capitalize(),
                    "total": int(total or 0),
                }
            )
        config = {
            "x_key": "status",
            "y_keys": ["total"],
            "labels": {"total": "Total de Pedidos"},
            "format": "number",
            "palette": ["#6366f1", "#10b981", "#f59e0b", "#ef4444"],
        }
        return config, dados

    elif query_key == "metricas_tokens_por_dia":
        stmt = (
            select(ConversaMensagem)
            .where(ConversaMensagem.metricas.is_not(None))
            .order_by(ConversaMensagem.criada_em.asc())
        )
        res = await session.scalars(stmt)
        mensagens = res.all()

        agrupado_por_dia: dict[str, dict[str, Any]] = {}
        for msg in mensagens:
            data_str = msg.criada_em.strftime("%Y-%m-%d")
            if data_str not in agrupado_por_dia:
                agrupado_por_dia[data_str] = {
                    "data": data_str,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "custo_usd": 0.0,
                }
            m = msg.metricas or {}
            p_tok = int(m.get("prompt_tokens") or m.get("promptTokens") or 0)
            c_tok = int(m.get("completion_tokens") or m.get("completionTokens") or 0)
            custo = float(m.get("estimated_cost_usd") or m.get("estimatedCostUsd") or 0.0)

            agrupado_por_dia[data_str]["prompt_tokens"] += p_tok
            agrupado_por_dia[data_str]["completion_tokens"] += c_tok
            agrupado_por_dia[data_str]["total_tokens"] += p_tok + c_tok
            agrupado_por_dia[data_str]["custo_usd"] += custo

        dados = sorted(agrupado_por_dia.values(), key=lambda d: d["data"])
        config = {
            "x_key": "data",
            "y_keys": ["prompt_tokens", "completion_tokens"],
            "labels": {
                "prompt_tokens": "Tokens de Entrada",
                "completion_tokens": "Tokens de Saída",
                "total_tokens": "Total de Tokens",
                "custo_usd": "Custo (USD)",
            },
            "format": "number",
            "palette": ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"],
        }
        return config, dados

    else:
        raise ValueError(f"Agregação não suportada: {query_key}")


async def generate_and_persist_chart(
    session: AsyncSession, prompt: str, user_email: str
) -> AdminChart | None:
    """Gera um gráfico a partir da intenção no prompt, persiste na tabela `admin_charts`
    e retorna o modelo `AdminChart` preenchido.
    """
    detected = detect_chart_request(prompt)
    if not detected:
        return None

    query_key = detected["query_key"]
    tipo_grafico = detected["tipo_grafico"]
    titulo = detected["titulo"]
    descricao = detected["descricao"]

    config_json, dados_json = await execute_chart_aggregation(session, query_key)

    chart = AdminChart(
        titulo=titulo,
        descricao=descricao,
        tipo_grafico=tipo_grafico,
        config_json=config_json,
        dados_json=dados_json,
        sql_query=query_key,
        fixado=True,
        ordem=0,
        criado_por=user_email or "admin",
    )
    session.add(chart)
    await session.commit()
    await session.refresh(chart)
    return chart
