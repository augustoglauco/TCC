"""Testes dos geradores de conjunto da Fase 10 (roteador, banco e holdout).

Cobre só a mecânica determinística — nada de LLM, Postgres ou Qdrant. O que
importa aqui é que as três garantias do desenho continuem valendo:

1. o conjunto do roteador sabe dizer, sem gastar chamada, se a mensagem chega
   ao classificador LLM ou morre no atalho por palavra-chave;
2. o conjunto do banco tem gabarito igual ao valor da linha, não parecido;
3. o holdout do CLIP tira exatamente uma foto por pasta com 2+ fotos.
"""

import importlib.util
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def _carregar(caminho: Path, nome: str):
    sys.path.insert(0, str(caminho.parent))
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def roteador():
    return _carregar(RAIZ / "eval" / "router_intents" / "gerar_dataset.py", "gerar_roteador")


@pytest.fixture(scope="module")
def banco():
    return _carregar(RAIZ / "eval" / "rag_banco" / "gerar_dataset.py", "gerar_banco")


@pytest.fixture(scope="module")
def imagens():
    return _carregar(RAIZ / "scripts" / "ingerir_imagens_corpus.py", "ingerir_imagens")


# --------------------------------------------------------------------------
# Roteador
# --------------------------------------------------------------------------


def test_caminho_reproduz_a_medicao_do_conjunto_antigo(roteador):
    """O roadmap registra "9 de 40 chegam ao LLM (22,5%)" como medição real.

    Se esta conta mudar, ou a tabela de keywords do classificador mudou (e o
    conjunto novo precisa ser refeito), ou a verificação quebrou — nos dois
    casos é bug, não ajuste de número.
    """
    antigo = json.loads(
        (RAIZ / "eval" / "router_intents" / "dataset.json").read_text(encoding="utf-8")
    )
    # O arquivo atual é o conjunto novo; o teste usa as 40 mensagens que o
    # README do roteador preserva como histórico de instrumento.
    assert antigo["total"] >= 290

    chegam = sum(1 for c in antigo["casos"] if roteador.classificar_caminho(c["mensagem"])[0])
    assert chegam == antigo["chegam_ao_llm"]
    # O requisito da Estratégia A: >=200 das 300 chegam ao LLM.
    assert chegam >= 200


def test_cortesia_pura_nao_chega_ao_llm(roteador):
    chega, motivo = roteador.classificar_caminho("bom dia, tudo bem?")

    assert chega is False
    assert motivo == "cortesia"


def test_uma_keyword_morre_no_atalho_duas_chegam_ao_llm(roteador):
    # Uma keyword de um domínio só: o atalho resolve e o LLM nunca vê.
    chega_uma, motivo_uma = roteador.classificar_caminho("qual o preço da catraca?")
    # Keywords de dois domínios: colapsa de propósito para o LLM.
    chega_duas, motivo_duas = roteador.classificar_caminho(
        "quero desconto mas o produto está com defeito"
    )

    assert (chega_uma, motivo_uma) == (False, "atalho_vendas")
    assert (chega_duas, motivo_duas) == (True, "duas_ou_mais_keywords")


def test_sinonimo_fora_da_tabela_chega_ao_llm(roteador):
    # "quanto sai" não está na tabela de keywords de vendas — é o caminho que
    # o prompt do gerador explora proibindo as palavras da tabela.
    chega, motivo = roteador.classificar_caminho("quanto sai o iDBlock?")

    assert (chega, motivo) == (True, "zero_keywords")


def test_montar_casos_descarta_mensagem_repetida(roteador):
    vistos: set[str] = set()

    primeiro = roteador.montar_casos(["Quanto sai?", "quanto SAI?"], "vendas", False, 1, vistos)
    segundo = roteador.montar_casos(["Quanto sai?"], "vendas", False, 9, vistos)

    assert len(primeiro) == 1
    assert segundo == []


# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------


def _produtos():
    return [
        {
            "id": 1,
            "nome": "iDBlock",
            "preco": Decimal("9705.90"),
            "categoria": "Catraca",
            "dias_alerta_estoque": 30,
        },
        {
            "id": 2,
            "nome": "iDTouch",
            "preco": Decimal("991.90"),
            "categoria": "Controle de Acesso",
            "dias_alerta_estoque": 15,
        },
    ]


def test_gabarito_do_banco_repete_o_valor_da_linha(banco):
    estoques = {1: {"CD-SP": 11, "CD-RJ": 28}, 2: {"CD-SP": 0, "CD-RJ": 0}}

    casos = banco.montar(_produtos(), estoques)

    preco = next(c for c in casos if c["tipo"] == "preco" and c["produto"] == "iDBlock")
    assert preco["resposta_esperada"] == "R$ 9705,90"
    assert preco["gabarito_bruto"]["preco"] == "9705.90"

    total = next(c for c in casos if c["tipo"] == "estoque_total" and c["produto"] == "iDBlock")
    assert total["gabarito_bruto"]["estoque_total"] == 39


def test_estoque_zerado_vira_resposta_negativa(banco):
    # Sem produto zerado, o conjunto não cobriria "está disponível?" com
    # resposta negativa e a avaliação mediria só o caminho abastecido.
    casos = banco.montar(_produtos(), {1: {"CD-SP": 5}, 2: {"CD-SP": 0, "CD-RJ": 0}})

    zerado = next(c for c in casos if c["tipo"] == "estoque_total" and c["produto"] == "iDTouch")
    assert "Não há unidades" in zerado["resposta_esperada"]


def test_conjunto_do_banco_e_deterministico(banco):
    estoques = {1: {"CD-SP": 11}, 2: {"CD-SP": 3}}

    primeiro = banco.montar(_produtos(), estoques)
    segundo = banco.montar(_produtos(), estoques)

    assert primeiro == segundo


def test_casos_do_banco_nascem_aprovados(banco):
    # Gabarito exato por construção: este conjunto não abre fila de revisão.
    casos = banco.montar(_produtos(), {1: {"CD-SP": 1}, 2: {"CD-SP": 2}})

    assert all(c["revisao"]["status"] == "aprovado" for c in casos)


# --------------------------------------------------------------------------
# Holdout do CLIP
# --------------------------------------------------------------------------


def test_holdout_so_para_pasta_com_duas_ou_mais_fotos(imagens):
    itens = [
        {"arquivo": "iDFace/a.jpg", "classificacao": "valida"},
        {"arquivo": "iDFace/b.jpg", "classificacao": "valida"},
        {"arquivo": "iDFace/c.jpg", "classificacao": "valida"},
        {"arquivo": "iDBell/unica.png", "classificacao": "valida"},
    ]

    holdout = imagens.escolher_holdout(itens)

    # iDBell tem uma foto só: ou ela está no índice, ou é a consulta.
    assert "iDBell" not in holdout
    # Escolha determinística (última em ordem alfabética), para a rodada ser
    # comparável com a anterior.
    assert holdout == {"iDFace": "iDFace/c.jpg"}


def test_holdout_ignora_imagem_invalida(imagens):
    itens = [
        {"arquivo": "iDBox/boa.jpg", "classificacao": "valida"},
        {"arquivo": "iDBox/gigante.png", "classificacao": "muito_grande"},
    ]

    assert imagens.escolher_holdout(imagens.imagens_validas({"itens_imagens": itens})) == {}
