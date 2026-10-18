"""Testes do gerador do conjunto de RAG documentos (Fase 10, Estratégia A).

Cobre a mecânica que não depende do LLM nem de rede: seleção e cota dos
documentos, conferência do `trecho_origem`, montagem dos casos e leitura do
array JSON que o modelo devolve. A rodada real chama o OpenRouter e está
descrita em `eval/rag_quality/README.md`.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
PASTA = EVAL_DIR / "rag_quality"


@pytest.fixture(scope="module")
def gerador():
    # Mesmo padrão de `test_rag_ingestion_eval.py`: o script vive em `eval/`,
    # fora do pacote `app` instalado no venv.
    sys.path.insert(0, str(PASTA))
    spec = importlib.util.spec_from_file_location("gerar_dataset", PASTA / "gerar_dataset.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["gerar_dataset"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _auditoria():
    return {
        "corpus": "docs/Manuais_fornecedor/ControlId",
        "itens_pdfs": [
            {"arquivo": "A/grande.pdf", "chars": 9000, "classificacao": "util"},
            {"arquivo": "B/medio.pdf", "chars": 5000, "classificacao": "util"},
            {"arquivo": "C/vazio.pdf", "chars": 20, "classificacao": "degenerado"},
            {"arquivo": "D/pequeno.pdf", "chars": 1000, "classificacao": "util"},
        ],
    }


def test_elegiveis_descartam_degenerados_e_ordenam_por_texto(gerador):
    # Os 11 degenerados da auditoria incluem os 8 PDFs de imagem pura, que
    # ficaram com 0 chunks na ingestão: pergunta derivada deles seria
    # impossível de responder e contaminaria a medida de alucinação, que
    # tem de vir só das 20 deliberadas.
    docs = gerador.documentos_elegiveis(_auditoria())

    assert [d["arquivo"] for d in docs] == ["A/grande.pdf", "B/medio.pdf", "D/pequeno.pdf"]


def test_cota_para_quando_a_meta_acaba(gerador):
    docs = gerador.documentos_elegiveis(_auditoria())
    plano = gerador.cota_por_documento(docs, total=3, por_documento=2)

    assert [(d["arquivo"], n) for d, n in plano] == [("A/grande.pdf", 2), ("B/medio.pdf", 1)]


def test_cota_nao_passa_do_teto_por_documento(gerador):
    docs = gerador.documentos_elegiveis(_auditoria())
    plano = gerador.cota_por_documento(docs, total=100, por_documento=2)

    assert sum(n for _, n in plano) == 6  # 3 documentos x 2
    assert all(n <= 2 for _, n in plano)


def test_trecho_confere_ignora_espaco_e_caixa(gerador):
    texto = "Sensor  biométrico\nÓtico 500 DPI"

    assert gerador.trecho_confere("sensor biométrico ótico 500 dpi", texto) is True
    assert gerador.trecho_confere("sensor capacitivo 1000 DPI", texto) is False
    assert gerador.trecho_confere("", texto) is False


def test_montar_casos_marca_trecho_parafraseado(gerador):
    # O `trecho_origem` existe para a revisão ser leitura lado a lado. Se o
    # modelo reescreve em vez de copiar, o campo passa a enganar o revisor —
    # daí a marca, em vez de descartar o caso em silêncio.
    texto = "Alimentação: 12 Vdc. Consumo máximo de 2 A."
    brutos = [
        {
            "pergunta": "Qual a tensão?",
            "resposta_esperada": "12 Vdc",
            "trecho_origem": "Alimentação: 12 Vdc",
            "dificuldade": "facil",
        },
        {
            "pergunta": "Qual o consumo?",
            "resposta_esperada": "2 A",
            "trecho_origem": "o consumo é de dois amperes",
            "dificuldade": "media",
        },
    ]

    casos = gerador.montar_casos(brutos, "datasheet.pdf", texto, proximo_id=7)

    assert [c["id"] for c in casos] == [7, 8]
    assert casos[0]["trecho_confere"] is True
    assert casos[1]["trecho_confere"] is False
    assert all(c["documento_origem"] == "datasheet.pdf" for c in casos)
    assert all(c["revisao"]["status"] == "pendente" for c in casos)
    assert all(c["sem_resposta"] is False for c in casos)


def test_montar_casos_descarta_item_incompleto_e_normaliza_dificuldade(gerador):
    brutos = [
        {"pergunta": "", "resposta_esperada": "x"},
        {"pergunta": "Tem Wi-Fi?", "resposta_esperada": ""},
        {"pergunta": "Tem PoE?", "resposta_esperada": "Sim", "dificuldade": "impossivel"},
    ]

    casos = gerador.montar_casos(brutos, "d.pdf", "texto", proximo_id=1)

    assert len(casos) == 1
    assert casos[0]["dificuldade"] == "media"


def test_casos_sem_resposta_nao_tem_documento_de_origem(gerador):
    # `run_eval.py` compara a fonte recuperada com `documento_origem`; num
    # caso sem resposta no corpus não existe fonte certa, e qualquer valor
    # aqui marcaria acerto ou erro por acidente.
    casos = gerador.montar_casos_sem_resposta(
        [{"pergunta": "Vocês têm catraca com leitor de íris?", "motivo_ausencia": "não há"}],
        proximo_id=161,
    )

    assert casos[0]["documento_origem"] == ""
    assert casos[0]["sem_resposta"] is True
    assert casos[0]["id"] == 161
    assert "não tem essa informação" in casos[0]["resposta_esperada"]


def test_parse_array_aceita_cerca_de_codigo_e_objeto_embrulhado(gerador):
    cercado = '```json\n[{"pergunta": "a", "resposta_esperada": "b"}]\n```'
    embrulhado = '{"perguntas": [{"pergunta": "a", "resposta_esperada": "b"}]}'

    assert gerador._parse_array(cercado)[0]["pergunta"] == "a"
    assert gerador._parse_array(embrulhado)[0]["pergunta"] == "a"


def test_envelope_conta_as_duas_metades(gerador):
    casos = [
        {"id": 1, "sem_resposta": False},
        {"id": 2, "sem_resposta": False},
        {"id": 3, "sem_resposta": True},
    ]

    env = gerador.envelope(casos, "modelo:free", "corpus")

    assert env["respondiveis"] == 2
    assert env["sem_resposta"] == 1
    assert "revisão humana" in env["observacao"]


def test_carregar_existente_tolera_arquivo_invalido(gerador, tmp_path):
    bom = tmp_path / "bom.json"
    bom.write_text(json.dumps({"casos": [{"id": 1}]}), encoding="utf-8")
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{nao é json", encoding="utf-8")

    assert gerador.carregar_existente(bom)["casos"] == [{"id": 1}]
    assert gerador.carregar_existente(ruim) == {}
    assert gerador.carregar_existente(tmp_path / "ausente.json") == {}


def test_marcar_duplicadas_aponta_para_o_primeiro(gerador):
    # Sem o produto no enunciado, a mesma pergunta em dois documentos faz a
    # pontuação de fonte reprovar uma das duas por construção — e numa fila
    # de um item por vez a repetição passaria batida.
    casos = [
        {"id": 1, "pergunta": "Qual a capacidade de usuários?"},
        {"id": 2, "pergunta": "Qual o consumo?"},
        {"id": 3, "pergunta": "qual a  capacidade de USUÁRIOS?"},
    ]

    gerador.marcar_duplicadas(casos)

    assert "duplicada_de" not in casos[0]
    assert "duplicada_de" not in casos[1]
    assert casos[2]["duplicada_de"] == 1


def test_prompt_exige_o_produto_na_pergunta(gerador):
    # Regressão da rodada de 2026-10-17: 56% das perguntas saíram sem dizer
    # de qual produto falavam ("qual a capacidade máxima de usuários?"), num
    # acervo de 37 linhas de produto. A regra no prompt é o que impede isso.
    assert "de qual produto ou modelo ela fala" in gerador._PROMPT_PERGUNTAS
    assert "data de revisão" in gerador._PROMPT_PERGUNTAS
