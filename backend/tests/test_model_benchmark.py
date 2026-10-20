"""Testes do orquestrador do benchmark de modelos locais (Fase 10).

Cobre a mecânica que não depende de GPU: agregação de métricas, retomada
entre rodadas, p95 e a detecção de JSON de classificação inválido. A rodada
real (Ollama + modelos de 8-14B) não é testável em CI — ver
`eval/model_benchmark/README.md`.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
_MODULO = EVAL_DIR / "model_benchmark" / "run_benchmark.py"


def _carregar_modulo():
    # O script vive em `eval/`, fora do pacote `app` instalado no venv, e
    # ele próprio insere `eval/` no sys.path para importar os outros evals.
    sys.path.insert(0, str(EVAL_DIR))
    spec = importlib.util.spec_from_file_location("run_benchmark", _MODULO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


bench = _carregar_modulo()


class _RespostaFalsa(BaseModel):
    text: str


class _ClienteFalso:
    """Devolve, em ordem, os textos dados — sem rede nem Ollama."""

    def __init__(self, textos: list[str]) -> None:
        self._textos = list(textos)
        self.chamadas = 0

    async def generate(self, prompt: str) -> _RespostaFalsa:
        self.chamadas += 1
        return _RespostaFalsa(text=self._textos.pop(0))


CANDIDATO = {
    "id": "modelo-teste",
    "rotulo": "Modelo de Teste",
    "ollama": "teste:8b",
    "familia": "teste",
    "parametros_b": 8,
    "quantizacao": "Q4_K_M",
}


def test_percentil_95_interpola_entre_os_dois_pontos_vizinhos():
    # Com 11 pontos, k = 0.95 * 10 = 9.5 -> meio do caminho entre o 10o
    # (valor 10) e o 11o (valor 11). Pegar o índice inteiro devolveria 11,
    # colando o p95 no máximo — o que apaga a diferença entre candidatos
    # nas amostras pequenas deste benchmark.
    assert bench.percentil_95([float(n) for n in range(1, 12)]) == 10.5


def test_percentil_95_sem_amostra_e_com_uma_so():
    assert bench.percentil_95([]) is None
    assert bench.percentil_95([2.5]) == 2.5


@pytest.mark.asyncio
async def test_cliente_instrumentado_conta_json_de_classificacao_invalido():
    # Por que medir isto à parte: quando o modelo devolve JSON quebrado, o
    # classificador cai para a heurística mantendo
    # provider_efetivo="heuristica_llm" — de fora, a falha de formato é
    # indistinguível de um acerto.
    #
    # "Válido" aqui é o schema inteiro de `ClassificationResult`
    # (domain + complexity + confidence), não só "é JSON": o terceiro caso
    # abaixo tem sintaxe perfeita e falta `confidence`, e o classificador
    # descarta igual. É essa a exigência que o benchmark compara entre
    # candidatos.
    cliente = bench.ClienteInstrumentado(
        _ClienteFalso(
            [
                '{"domain": "vendas", "complexity": "baixa", "confidence": 0.9}',
                "Claro! Acho que é sobre vendas.",
                '{"domain": "suporte", "complexity": "alta"}',
                '```json\n{"domain": "suporte", "complexity": "alta", "confidence": 0.7}\n```',
            ]
        )
    )
    cliente.checar_json_classificacao = True

    for _ in range(4):
        await cliente.generate("qualquer")

    # 1o e 4o passam (o 4o vem em cerca de código, que `strip_code_fence`
    # remove); o 2o não é JSON e o 3o não tem `confidence`.
    assert cliente.json_validos == 2
    assert cliente.json_invalidos == 2
    assert len(cliente.latencias_s) == 4


@pytest.mark.asyncio
async def test_cliente_instrumentado_so_checa_json_quando_pedido():
    cliente = bench.ClienteInstrumentado(_ClienteFalso(["resposta em prosa"]))

    await cliente.generate("qualquer")

    assert cliente.json_invalidos == 0
    assert cliente.json_validos == 0
    assert len(cliente.latencias_s) == 1


def test_acerto_de_categoria_ignora_acento():
    # Achado ao rodar a etapa `imagem` pela primeira vez (2026-10-16): o
    # modelo responde "identificador biométrico" e o termo aceito no
    # dataset é "biometri" — sem normalizar acento, 3 acertos viravam erro.
    assert bench._acertou_categoria("identificador biométrico", ["biometri"])
    assert bench._acertou_categoria("CATRACA eletrônica", ["catraca"])
    assert bench._acertou_categoria("leitor facial", ["reconhecimento", "facial"])
    assert not bench._acertou_categoria("torneira eletrônica", ["catraca", "impressora"])


class _VisaoFalsa(BaseModel):
    e_do_portfolio: bool
    produto: str


def test_pontuar_imagem_cobra_categoria_so_em_positivo_com_aceitos():
    positivo = {"e_do_portfolio": True, "aceitos": ["catraca"]}
    assert bench._pontuar_imagem(positivo, _VisaoFalsa(e_do_portfolio=True, produto="Catraca")) == (
        True,
        True,
    )
    sem_aceitos = {"e_do_portfolio": True}
    assert bench._pontuar_imagem(sem_aceitos, _VisaoFalsa(e_do_portfolio=True, produto="x")) == (
        True,
        None,
    )
    negativo = {"e_do_portfolio": False, "aceitos": ["catraca"]}
    assert bench._pontuar_imagem(negativo, _VisaoFalsa(e_do_portfolio=True, produto="x")) == (
        False,
        None,
    )


@pytest.mark.asyncio
async def test_etapa_imagem_sem_capability_registra_queda_para_visao_externa():
    # Modelo text-only não é pulado em silêncio: `suportado_localmente:
    # false` é o resultado, e significa que a imagem do cliente iria para a
    # visão externa (custo por token e a imagem saindo da máquina).
    resultado = await bench.etapa_imagem(inner=None, tem_visao=False)

    assert resultado["suportado_localmente"] is False
    assert "visão externa" in resultado["observacao"]
    assert resultado["latencias_s"] == []

    envelope = {"metricas": {}, "itens": {"imagem": resultado}}
    bench.consolidar_metricas(envelope)

    assert envelope["metricas"]["visao_local"] is False
    # Sem capability não há taxa a reportar — e um 0.0 aqui seria pior que a
    # ausência: leria como "errou tudo" em vez de "não se aplica".
    assert "imagem_portfolio_acerto" not in envelope["metricas"]


def test_dataset_de_imagens_tem_pelo_menos_um_caso_negativo():
    # Sem negativo, um modelo que responde `e_do_portfolio: true` para
    # qualquer imagem marca 100% — foi o que o conjunto só-positivos da
    # primeira versão teria reportado.
    caminho = EVAL_DIR / "model_benchmark" / "imagens" / "dataset.json"
    casos = json.loads(caminho.read_text(encoding="utf-8"))["casos"]

    assert any(not c["e_do_portfolio"] for c in casos)
    assert any(c["e_do_portfolio"] for c in casos)


def test_dataset_de_imagens_aponta_para_arquivos_que_existem():
    caminho = EVAL_DIR / "model_benchmark" / "imagens" / "dataset.json"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    repo = EVAL_DIR.parents[1]

    assert dados["casos"], "dataset de imagens vazio"
    for caso in dados["casos"]:
        imagem = repo / caso["caminho"]
        assert imagem.is_file(), f"{caso['id']}: imagem não encontrada em {imagem}"
        # Vazio é válido: a categoria só é cobrada onde há `aceitos` (ver
        # `montar_dataset_imagem.py`); nos demais vale só `e_do_portfolio`.
        assert isinstance(caso["aceitos"], list), f"{caso['id']}: `aceitos` não é lista"
        assert isinstance(caso["e_do_portfolio"], bool)


def test_consolidar_metricas_agrega_latencia_de_todas_as_etapas():
    # A latência precisa sair do conjunto de etapas presentes no arquivo,
    # não só da última rodada: senão uma execução retomada reportaria um
    # número diferente de uma execução única com as mesmas etapas.
    envelope = {
        "metricas": {},
        "itens": {
            "roteador": {
                "acuracia": 0.9,
                "acertos": 36,
                "total": 40,
                "json_invalido_taxa": 0.05,
                "latencias_s": [1.0, 2.0],
            },
            "injecao": {
                "taxa_resistencia": 0.75,
                "comprometidos": 2,
                "total": 8,
                "latencias_s": [3.0, 4.0],
            },
        },
    }

    bench.consolidar_metricas(envelope)

    metricas = envelope["metricas"]
    assert metricas["roteador_acuracia"] == 0.9
    assert metricas["json_invalido_taxa"] == 0.05
    assert metricas["injecao_resistencia"] == 0.75
    assert metricas["chamadas_medidas"] == 4
    assert metricas["latencia_media_s"] == 2.5


def test_etapas_pendentes_pula_o_que_ja_foi_gravado():
    envelope = {"itens": {"roteador": {}}}

    assert bench.etapas_pendentes(envelope, ["roteador", "injecao"], forcar=False) == ["injecao"]
    assert bench.etapas_pendentes(envelope, ["roteador", "injecao"], forcar=True) == [
        "roteador",
        "injecao",
    ]


def test_envelope_roundtrip_mantem_o_formato_que_a_api_publica_le(tmp_path, monkeypatch):
    # `app.api.avaliacao._modelos` só aceita o arquivo se `metricas` for um
    # dict; e expõe modelo/gerado_em/config/metricas, nunca `itens`.
    monkeypatch.setattr(bench, "RESULTS_DIR", tmp_path)

    envelope = bench.carregar_envelope(CANDIDATO)
    assert envelope["itens"] == {}
    assert envelope["modelo"] == "Modelo de Teste"

    envelope["itens"]["roteador"] = {
        "acuracia": 0.8,
        "acertos": 32,
        "total": 40,
        "json_invalido_taxa": 0.0,
        "latencias_s": [1.5],
    }
    bench.consolidar_metricas(envelope)
    caminho = bench.gravar_envelope(CANDIDATO, envelope)

    gravado = json.loads(caminho.read_text(encoding="utf-8"))
    assert gravado["versao"] == bench.VERSAO_ENVELOPE
    assert gravado["avaliacao"] == "model_benchmark"
    assert gravado["gerado_em"] is not None
    assert isinstance(gravado["metricas"], dict)
    assert gravado["metricas"]["roteador_acuracia"] == 0.8

    # Segunda abertura: a etapa já gravada é vista como pronta (retomada).
    relido = bench.carregar_envelope(CANDIDATO)
    assert bench.etapas_pendentes(relido, ["roteador", "rag"], forcar=False) == ["rag"]


def test_carregar_candidatos_filtra_por_id_e_recusa_id_desconhecido():
    todos = bench.carregar_candidatos(None)
    assert len(todos) >= 1
    primeiro = todos[0]["id"]

    assert [c["id"] for c in bench.carregar_candidatos([primeiro])] == [primeiro]

    with pytest.raises(SystemExit, match="desconhecido"):
        bench.carregar_candidatos(["nao-existe"])


def test_modelos_json_tem_tag_ollama_unica_por_candidato():
    candidatos = bench.carregar_candidatos(None)
    tags = [c["ollama"] for c in candidatos]
    ids = [c["id"] for c in candidatos]

    assert len(set(tags)) == len(tags)
    assert len(set(ids)) == len(ids)
    for candidato in candidatos:
        assert set(candidato) >= {
            "id",
            "rotulo",
            "ollama",
            "familia",
            "parametros_b",
            "quantizacao",
        }
