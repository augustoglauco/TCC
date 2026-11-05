from src.app import (
    calcular_resumo_cotacao,
    calcular_total_pedido,
    centros_que_atendem,
    formatar_itens_carrinho,
    formatar_itens_pedido,
    formatar_moeda,
    linhas_carrinho,
    linhas_pedido,
    necessidade_por_produto,
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
        "itens": [
            {
                "produto_id": 1,
                "quantidade": 2,
                "preco_unitario": 100.0,
                "percentual_desconto_aplicado": 0,
            }
        ],
        "total": 200.0,
    }
    resumo = calcular_resumo_cotacao(cotacao)
    assert resumo == {"subtotal_bruto": 200.0, "desconto_total": 0.0, "total": 200.0}


def test_calcular_resumo_cotacao_com_desconto():
    # o servidor devolve o preço ANTES do desconto (100) e o total já com ele (180)
    cotacao = {
        "itens": [
            {
                "produto_id": 1,
                "quantidade": 2,
                "preco_unitario": 100.0,
                "percentual_desconto_aplicado": 10,
            }
        ],
        "total": 180.0,
    }
    resumo = calcular_resumo_cotacao(cotacao)
    assert resumo["subtotal_bruto"] == 200.0
    assert resumo["desconto_total"] == 20.0
    assert resumo["total"] == 180.0


def test_calcular_total_pedido():
    pedido = {
        "itens": [
            {
                "produto_id": 1,
                "quantidade": 2,
                "preco_unitario": 100.0,
                "centro_distribuicao": "SP",
            },
            {"produto_id": 2, "quantidade": 1, "preco_unitario": 50.0, "centro_distribuicao": "SP"},
        ]
    }
    assert calcular_total_pedido(pedido) == 250.0


def test_necessidade_por_produto_soma_repetidos():
    carrinho = [
        {"produto_id": 1, "quantidade": 2},
        {"produto_id": 2, "quantidade": 1},
        {"produto_id": 1, "quantidade": 3},
    ]
    assert necessidade_por_produto(carrinho) == {1: 5, 2: 1}


def test_centros_que_atendem_exige_saldo_em_todos_os_itens():
    carrinho = [{"produto_id": 1, "quantidade": 5}, {"produto_id": 2, "quantidade": 3}]
    saldos = {1: {"SP": 10, "RJ": 4}, 2: {"SP": 3, "RJ": 9}}
    assert centros_que_atendem(carrinho, saldos) == ["SP"]


def test_centros_que_atendem_soma_o_mesmo_produto_repetido():
    carrinho = [{"produto_id": 1, "quantidade": 3}, {"produto_id": 1, "quantidade": 3}]
    assert centros_que_atendem(carrinho, {1: {"SP": 5, "RJ": 6}}) == ["RJ"]


def test_centros_que_atendem_sem_saldo_devolve_vazio():
    carrinho = [{"produto_id": 1, "quantidade": 5}]
    assert centros_que_atendem(carrinho, {1: {"SP": 1}}) == []
    assert centros_que_atendem(carrinho, {}) == []


def test_linhas_carrinho_usa_nome_ou_generico():
    linhas = linhas_carrinho(
        [{"produto_id": 1, "quantidade": 2}, {"produto_id": 9, "quantidade": 1}], {1: "Catraca"}
    )
    assert linhas[0] == {"ID": 1, "Produto": "Catraca", "Quantidade": 2}
    assert linhas[1]["Produto"] == "Produto 9"


def test_linhas_pedido_calcula_subtotal():
    pedido = {
        "itens": [
            {"produto_id": 1, "quantidade": 2, "preco_unitario": 100.0, "centro_distribuicao": "SP"}
        ]
    }
    linha = linhas_pedido(pedido, {1: "Catraca"})[0]
    assert linha["Produto"] == "Catraca"
    assert linha["CD"] == "SP"
    assert linha["Subtotal"] == "R$ 200,00"
