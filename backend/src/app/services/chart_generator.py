"""Gate de intenção para o Agente Analítico de Gráficos Dinâmicos
(`app.services.analytics_agent`).

Decisão registrada em docs/ARCHITECTURE.md §5 ("Agente Analítico de
Gráficos Dinâmicos", 2026-10-06): este módulo não gera gráfico — gráfico
novo é sempre Text-to-SQL via LLM. `detect_chart_request` só decide "esta
mensagem parece um pedido de gráfico?" (heurística por palavra-chave) antes
do orquestrador acionar o LLM, evitando gastar uma chamada em mensagens que
claramente não pedem gráfico nenhum.

Achado de 2026-10-06: a versão anterior deste módulo também expunha
`execute_chart_aggregation`/`SUPPORTED_QUERIES` (agregações SQL fixas) —
usadas só para recalcular gráficos salvos antes desta revisão com uma
`query_key` fixa. Confirmado que não há mais gráfico assim em uso, então
esse código (e o terceiro caminho do refresh em `app.api.admin_charts`) foi
removido, não só desativado.
"""


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
        for v in [
            "valor",
            "valores",
            "faturamento",
            "receita",
            "reais",
            "r$",
            "dinheiro",
            "preço",
            "preco",
        ]
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

    if any(
        k in texto for k in ["estoque", "cd", "centro de distribuição", "centros de distribuicao"]
    ):
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
