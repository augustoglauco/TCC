from src.app import (
    formatar_moeda,
    formatar_itens_carrinho,
    formatar_itens_pedido,
    calcular_resumo_cotacao,
    calcular_total_pedido,
)


def test_formatar_moeda():
    assert formatar_moeda(1250.5) == "R$ 1.250,50"
    assert formatar_moeda(0) == "R$ 0,00"


def test_formatar_itens_carrinho():
    carrinho = [{"produto_id": 1, "quantidade": 5}]
    itens_mcp = formatar_itens_carrinho(carrinho)
    assert itens_mcp == [{"produto_id": 1, "quantidade": 5}]


def test_formatar_itens_pedido():
    carrinho = [{"produto_id": 1, "quantidade": 5}, {"produto_id": 2, "quantidade": 1}]
    itens_mcp = formatar_itens_pedido(carrinho, "SP")
    assert itens_mcp == [
        {"produto_id": 1, "quantidade": 5, "centro_distribuicao": "SP"},
        {"produto_id": 2, "quantidade": 1, "centro_distribuicao": "SP"},
    ]


def test_calcular_resumo_cotacao_sem_desconto():
    cotacao = {
        "itens": [{"produto_id": 1, "quantidade": 2, "preco_unitario": 100.0, "percentual_desconto_aplicado": 0}],
        "total": 200.0,
    }
    resumo = calcular_resumo_cotacao(cotacao)
    assert resumo == {"subtotal_bruto": 200.0, "desconto_total": 0.0, "total": 200.0}


def test_calcular_resumo_cotacao_com_desconto():
    # preço líquido 90 com 10% de desconto -> preço cheio 100
    cotacao = {
        "itens": [{"produto_id": 1, "quantidade": 2, "preco_unitario": 90.0, "percentual_desconto_aplicado": 10}],
        "total": 180.0,
    }
    resumo = calcular_resumo_cotacao(cotacao)
    assert resumo["subtotal_bruto"] == 200.0
    assert resumo["desconto_total"] == 20.0
    assert resumo["total"] == 180.0


def test_calcular_total_pedido():
    pedido = {
        "itens": [
            {"produto_id": 1, "quantidade": 2, "preco_unitario": 100.0, "centro_distribuicao": "SP"},
            {"produto_id": 2, "quantidade": 1, "preco_unitario": 50.0, "centro_distribuicao": "SP"},
        ]
    }
    assert calcular_total_pedido(pedido) == 250.0
