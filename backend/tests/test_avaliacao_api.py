"""Testes de `GET /api/avaliacao/resultados` (página pública)."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.avaliacao import intervalo_wilson
from app.api.avaliacao import router as avaliacao_router
from app.config import get_settings


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(avaliacao_router)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def eval_em(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "eval_dir", str(tmp_path))
    return tmp_path


def _gravar(base, rel, dados):
    arq = base / rel
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados), encoding="utf-8")


def test_wilson_valores_conhecidos():
    p = intervalo_wilson(14, 18)
    assert p.taxa == pytest.approx(0.7778, abs=1e-4)
    assert 0.54 < p.ic_inf < 0.57
    assert 0.90 < p.ic_sup < 0.93
    assert intervalo_wilson(0, 0).total == 0


def test_publico_sem_token_e_vazio_sem_arquivos(client, eval_em):
    r = client.get("/api/avaliacao/resultados")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["roteador"] is None and corpo["rag"] is None
    assert corpo["modelos"] == []


def test_agrega_sem_vazar_respostas(client, eval_em):
    _gravar(
        eval_em,
        "rag_quality/results.json",
        {
            "casos": [
                {
                    "id": 1,
                    "pergunta": "SEGREDO-P",
                    "dificuldade": "facil",
                    "resposta_gerada": "SEGREDO-R",
                    "fontes_recuperadas": ["x.pdf"],
                    "fonte_correta": True,
                    "nota_llm_judge": {"nota": 4, "justificativa": "SEGREDO-J"},
                },
                {
                    "id": 2,
                    "pergunta": "q",
                    "dificuldade": "dificil",
                    "resposta_gerada": "r",
                    "fonte_correta": False,
                    "nota_llm_judge": {"nota": 2},
                },
            ]
        },
    )
    _gravar(
        eval_em,
        "prompt_injection/results.json",
        {
            "local": {
                "cliente": "local",
                "total_casos": 2,
                "comprometidos": 1,
                "casos": [
                    {
                        "categoria": "injecao_direta",
                        "comprometido": False,
                        "resposta_gerada": "SEGREDO-I",
                    },
                    {"categoria": "injecao_indireta_rag", "comprometido": True},
                ],
            }
        },
    )
    _gravar(
        eval_em,
        "model_benchmark/results/m.json",
        {"modelo": "m", "metricas": {"rag_nota_media": 3.1}, "itens": [{"resposta": "SEGREDO-B"}]},
    )
    r = client.get("/api/avaliacao/resultados")
    corpo = r.json()
    assert corpo["rag"]["nota_media"] == 3.0
    assert corpo["rag"]["fonte_correta"]["acertos"] == 1
    assert corpo["injecao"]["clientes"][0]["resistencia"]["taxa"] == 0.5
    assert corpo["modelos"][0]["metricas"]["rag_nota_media"] == 3.1
    assert "SEGREDO" not in r.text


def test_chunk_size_usa_grade_da_etapa3_com_melhor_overlap(client, eval_em):
    def ponto(cs, ov, ndcg, r5):
        return {
            "chunk_size": cs,
            "overlap_pct": ov,
            "metricas_sem_corte": {"ndcg@10": ndcg, "recall": {"@5": r5}},
            "itens": ["SEGREDO"],
        }

    _gravar(
        eval_em,
        "rag_ingestion/resultados_etapa3.json",
        {"pontos": [ponto(512, 10, 0.5, 0.6), ponto(512, 15, 0.7, 0.8), ponto(128, 15, 0.4, 0.5)]},
    )
    corpo = client.get("/api/avaliacao/resultados").json()["chunk_size"]
    assert [p["chunk_size"] for p in corpo["pontos"]] == [128, 512]
    assert corpo["pontos"][1] == {
        "chunk_size": 512,
        "overlap_pct": 15,
        "ndcg_10": 0.7,
        "recall_5": 0.8,
    }
    assert corpo["melhor_chunk_size"] == 512
    assert "SEGREDO" not in json.dumps(corpo)


def test_arquivo_corrompido_vira_secao_vazia(client, eval_em):
    (eval_em / "router_intents").mkdir()
    (eval_em / "router_intents" / "results.json").write_text("{quebrado")
    assert client.get("/api/avaliacao/resultados").json()["roteador"] is None


def test_etapa7_e_sem_resposta_sao_agregados(client, eval_em):
    _gravar(
        eval_em,
        "rag_quality/results.json",
        {
            "casos": [
                {"nota_llm_judge": {"nota": 4}, "fonte_correta": True, "dificuldade": "facil"}
            ],
            "casos_sem_resposta": [
                {"recusou": True, "alucinou": False},
                {"recusou": False, "alucinou": True},
            ],
        },
    )
    braco = {"braco": "vencedora", "fonte_correta": 9, "respondiveis": 10}
    _gravar(eval_em, "rag_quality/etapa7.json", {"bracos": [braco]})
    corpo = client.get("/api/avaliacao/resultados").json()
    assert corpo["rag"]["sem_resposta"] == {"total": 2, "recusou": 1, "alucinou": 1}
    assert corpo["etapa7"]["bracos"][0]["fonte_correta_ic"]["total"] == 10
