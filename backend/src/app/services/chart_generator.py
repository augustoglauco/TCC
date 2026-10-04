"""Serviço de geração e agregação analítica de gráficos dinâmicos para Administradores.

Executa consultas analíticas pré-compiladas e seguras (SQLAlchemy) e persiste
definições e dados na tabela `admin_charts`.
"""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AdminChart, ConversaMensagem, Pedido, Produto, ProdutoEstoque

logger = logging.getLogger("assistente.chart_generator")

SUPPORTED_QUERIES = {
    "vendas_por_categoria": "Distribuição de produtos e valor por categoria",
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

    # Detecta agregação / query alvo
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
    else:
        query_key = "vendas_por_categoria"
        titulo = "Produtos e Vendas por Categoria"
        descricao = "Total estimado e quantidade de itens cadastrados por categoria"

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
    if query_key == "vendas_por_categoria":
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
