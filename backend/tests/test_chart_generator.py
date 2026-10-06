from app.services.chart_generator import detect_chart_request


def test_detect_chart_request():
    assert detect_chart_request("gere um gráfico de vendas por categoria") is not None
    res = detect_chart_request("mostre o estoque num gráfico de pizza")
    assert res is not None
    assert res["tipo_grafico"] == "pie"
    assert res["query_key"] == "estoque_por_cd"

    # Intenção solicitada pelo usuário: "gere grafico de venda de produtos x quantidade"
    res_qtd = detect_chart_request("gere grafico de venda de produtos x quantidade")
    assert res_qtd is not None
    assert res_qtd["query_key"] == "vendas_produtos_quantidade"
    assert res_qtd["titulo"] == "Vendas por Produto (Quantidade)"
    assert res_qtd["tipo_grafico"] == "bar"

    # Intenção por faturamento/valor
    res_val = detect_chart_request("gráfico de venda de produtos por faturamento")
    assert res_val is not None
    assert res_val["query_key"] == "vendas_produtos_valor"
    assert res_val["titulo"] == "Vendas por Produto (Faturamento)"

    # Categoria por quantidade
    res_cat_qtd = detect_chart_request("gráfico de quantidade por categoria")
    assert res_cat_qtd is not None
    assert res_cat_qtd["query_key"] == "vendas_categoria_quantidade"

    # Não deve disparar para perguntas comuns
    assert detect_chart_request("como trocar meu produto?") is None
    assert detect_chart_request("quero saber o preço do alicate") is None
