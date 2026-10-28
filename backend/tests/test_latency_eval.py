"""Testes das funções puras de `eval/latency/run_eval.py` (sem LLM)."""

import importlib.util
from pathlib import Path

import pytest

CAMINHO = Path(__file__).parent.parent / "eval" / "latency" / "run_eval.py"


@pytest.fixture(scope="module")
def modulo():
    spec = importlib.util.spec_from_file_location("latency_run_eval", CAMINHO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_percentil_95_interpola(modulo):
    assert modulo.percentil_95([1.0, 2.0, 3.0, 4.0, 5.0]) == pytest.approx(4.8)
    assert modulo.percentil_95([7.0]) == 7.0


def test_resumo_agrega_tempos_tokens_e_custo(modulo):
    chamadas = [
        {"total_s": 1.0, "prompt_tokens": 100, "completion_tokens": 10, "custo_usd": 0.0},
        {"total_s": 3.0, "prompt_tokens": 300, "completion_tokens": None, "custo_usd": 0.002},
    ]
    r = modulo.resumir(chamadas)
    assert r["media_s"] == 2.0 and r["maximo_s"] == 3.0
    assert r["tokens_prompt_medio"] == 200 and r["tokens_saida_medio"] == 5
    assert r["custo_total_usd"] == 0.002


def test_amostra_e_estratificada_e_reprodutivel(modulo):
    a = modulo._amostra(5, 42)
    assert a == modulo._amostra(5, 42)
    assert {c["intencao_esperada"] for c in a} == set(modulo._DOMINIOS)
    assert len(a) == 20
