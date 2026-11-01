"""Testes dos helpers puros de `eval/rag_quality/run_eval.py` (seleção de casos)."""

import importlib.util
import sys
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parents[1] / "eval" / "rag_quality"


@pytest.fixture(scope="module")
def run_eval():
    sys.path.insert(0, str(PASTA))
    spec = importlib.util.spec_from_file_location("rq_run_eval", PASTA / "run_eval.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _caso(id_, status="aprovado", **extra):
    return {"id": id_, "revisao": {"status": status}, **extra}


CASOS = [
    _caso(1),
    _caso(2, "corrigido"),
    _caso(3, "descartado"),
    _caso(4, "pendente"),
    {"id": 5},
    _caso(6, duplicada_de=1),
    _caso(7, origem_ambigua=True),
    _caso(8, sem_resposta=True),
    _caso(9, "corrigido", sem_resposta=True),
    _caso(10, "descartado", sem_resposta=True),
    _caso(11, sem_resposta=True, duplicada_de=8),
    _caso(12, sem_resposta=True, origem_ambigua=True),
]


def _ids(casos):
    return [c["id"] for c in casos]


def test_respondiveis_revisados(run_eval):
    assert _ids(run_eval._so_respondiveis_revisados(CASOS)) == [1, 2]


def test_sem_resposta_revisados_ignora_origem_ambigua(run_eval):
    assert _ids(run_eval._so_sem_resposta_revisados(CASOS)) == [8, 9, 12]


def test_selecionar_casos_por_modo(run_eval):
    assert _ids(run_eval._selecionar_casos(CASOS, True, False)) == [8, 9, 12]
    assert _ids(run_eval._selecionar_casos(CASOS, False, True)) == [1, 2]
    assert _ids(run_eval._selecionar_casos(CASOS, False, False)) == [1, 2, 8, 9, 12]
