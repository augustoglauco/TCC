"""Testes do painel de preparação da avaliação (`/api/admin/datasets`).

Nenhum teste dispara processo de verdade: o executor de tarefas é
substituído, porque as tarefas reais levam de minutos (ingestão) a horas
(benchmark).
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import admin_datasets
from app.api.admin_datasets import router as datasets_router
from app.config import get_settings


@pytest.fixture
def eval_falso(tmp_path, monkeypatch):
    """Aponta `eval_dir` para um diretório temporário com dois conjuntos:
    um de revisão manual (roteador) e um automático (imagem)."""
    (tmp_path / "router_intents").mkdir()
    (tmp_path / "router_intents" / "dataset.json").write_text(
        json.dumps(
            {
                "casos": [
                    {"id": "r1", "mensagem": "o aparelho apita sem parar", "esperado": "suporte"},
                    {"id": "r2", "mensagem": "quanto custa o iDBox?", "esperado": "vendas"},
                    {
                        "id": "r3",
                        "mensagem": "quero remarcar",
                        "esperado": "agendamento",
                        "revisao": {"status": "aprovado", "em": "2026-10-16T12:00:00"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "model_benchmark" / "imagens").mkdir(parents=True)
    (tmp_path / "model_benchmark" / "imagens" / "dataset.json").write_text(
        json.dumps({"casos": [{"id": "pos_01", "e_do_portfolio": True}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(get_settings(), "eval_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def datasets_client(eval_falso):
    app = FastAPI()
    app.include_router(datasets_router)
    with TestClient(app) as test_client:
        yield test_client


def _sem_auth(client):
    """Dispensa o token de admin — o alvo destes testes é a lógica do
    painel, não a autenticação (coberta em `test_admin_auth.py`)."""
    from app.api.admin_auth import require_admin

    client.app.dependency_overrides[require_admin] = lambda: None
    return client


def test_listar_conjuntos_resume_progresso(datasets_client):
    client = _sem_auth(datasets_client)

    corpo = client.get("/api/admin/datasets").json()
    por_id = {c["id"]: c for c in corpo["conjuntos"]}

    roteador = por_id["roteador"]
    assert roteador["total"] == 3
    assert roteador["meta"] == 300
    assert roteador["pendentes"] == 2
    assert roteador["aprovados"] == 1
    assert roteador["existe"] is True


def test_conjunto_automatico_vem_todo_aprovado(datasets_client):
    # Gabarito exato por construção (nome da pasta / linha do banco): não
    # entra na fila de revisão, senão o desenvolvedor gastaria horas
    # confirmando o que não tem como estar errado.
    client = _sem_auth(datasets_client)

    por_id = {c["id"]: c for c in client.get("/api/admin/datasets").json()["conjuntos"]}

    assert por_id["rag_imagem"]["revisao_automatica"] is True
    assert por_id["rag_imagem"]["pendentes"] == 0
    assert por_id["rag_imagem"]["aprovados"] == 1


def test_imagem_conta_os_casos_contra_a_meta_de_72(datasets_client):
    client = _sem_auth(datasets_client)

    por_id = {c["id"]: c for c in client.get("/api/admin/datasets").json()["conjuntos"]}

    assert por_id["rag_imagem"]["total"] == 1
    assert por_id["rag_imagem"]["meta"] == 72


def test_geradores_dos_conjuntos_novos_estao_registrados():
    for tipo, script in (
        ("gerar_rascunho_roteador", "router_intents"),
        ("gerar_conjunto_banco", "rag_banco"),
        ("gerar_rascunho_injecao", "prompt_injection"),
    ):
        _, comando = admin_datasets.TAREFAS_DISPONIVEIS[tipo]
        assert comando[1] == f"eval/{script}/gerar_dataset.py"


def test_conjunto_ainda_nao_gerado_nao_quebra(datasets_client):
    # rag_banco e rag_quality nao existem no eval falso.
    client = _sem_auth(datasets_client)

    por_id = {c["id"]: c for c in client.get("/api/admin/datasets").json()["conjuntos"]}

    assert por_id["rag_banco"]["existe"] is False
    assert por_id["rag_banco"]["total"] == 0


def test_listar_itens_traz_so_pendentes_por_padrao(datasets_client):
    client = _sem_auth(datasets_client)

    corpo = client.get("/api/admin/datasets/roteador/itens").json()

    assert corpo["total"] == 2
    assert [i["id"] for i in corpo["itens"]] == ["r1", "r2"]
    # `campos` vai cru: a tela monta layout diferente por conjunto.
    assert corpo["itens"][0]["campos"]["mensagem"] == "o aparelho apita sem parar"
    assert "revisao" not in corpo["itens"][0]["campos"]


def test_listar_itens_com_todos_inclui_revisados(datasets_client):
    client = _sem_auth(datasets_client)

    corpo = client.get("/api/admin/datasets/roteador/itens?apenas_pendentes=false").json()

    assert corpo["total"] == 3
    assert corpo["itens"][2]["status"] == "aprovado"


def test_aprovar_item_grava_no_dataset(datasets_client, eval_falso):
    client = _sem_auth(datasets_client)

    resposta = client.patch("/api/admin/datasets/roteador/itens/0", json={"status": "aprovado"})

    assert resposta.status_code == 200
    gravado = json.loads(
        (eval_falso / "router_intents" / "dataset.json").read_text(encoding="utf-8")
    )
    assert gravado["casos"][0]["revisao"]["status"] == "aprovado"
    assert gravado["casos"][0]["revisao"]["em"]


def test_corrigir_item_altera_os_campos_pedidos(datasets_client, eval_falso):
    client = _sem_auth(datasets_client)

    resposta = client.patch(
        "/api/admin/datasets/roteador/itens/1",
        json={"status": "corrigido", "campos": {"esperado": "atendimento"}},
    )

    assert resposta.status_code == 200
    assert resposta.json()["campos"]["esperado"] == "atendimento"
    gravado = json.loads(
        (eval_falso / "router_intents" / "dataset.json").read_text(encoding="utf-8")
    )
    assert gravado["casos"][1]["esperado"] == "atendimento"


def test_item_descartado_continua_no_arquivo(datasets_client, eval_falso):
    # Apagar perderia o registro de que o caso foi considerado e rejeitado,
    # que é informação do experimento.
    client = _sem_auth(datasets_client)

    client.patch("/api/admin/datasets/roteador/itens/0", json={"status": "descartado"})

    gravado = json.loads(
        (eval_falso / "router_intents" / "dataset.json").read_text(encoding="utf-8")
    )
    assert len(gravado["casos"]) == 3
    assert gravado["casos"][0]["revisao"]["status"] == "descartado"


def test_revisar_conjunto_automatico_e_recusado(datasets_client):
    client = _sem_auth(datasets_client)

    resposta = client.patch("/api/admin/datasets/rag_imagem/itens/0", json={"status": "aprovado"})

    assert resposta.status_code == 409


def test_revisar_indice_fora_do_conjunto(datasets_client):
    client = _sem_auth(datasets_client)

    resposta = client.patch("/api/admin/datasets/roteador/itens/99", json={"status": "aprovado"})
    assert resposta.status_code == 404


def test_tarefa_desconhecida_e_recusada(datasets_client):
    client = _sem_auth(datasets_client)

    resposta = client.post("/api/admin/datasets/tarefas", json={"tipo": "formatar_o_hd"})

    assert resposta.status_code == 404


@pytest.mark.asyncio
async def test_tarefa_roda_e_registra_log(datasets_client, monkeypatch):
    client = _sem_auth(datasets_client)
    admin_datasets._tarefas.clear()

    async def _falso(tarefa, raiz):
        tarefa.linhas.append("linha 1")
        tarefa.linhas.append("linha 2")
        tarefa.estado = "concluida"
        tarefa.codigo = 0

    monkeypatch.setattr(admin_datasets, "_acompanhar", _falso)

    criada = client.post("/api/admin/datasets/tarefas", json={"tipo": "ingerir_corpus"}).json()
    assert criada["estado"] == "rodando"

    detalhe = client.get(f"/api/admin/datasets/tarefas/{criada['id']}").json()
    assert detalhe["linhas"] == ["linha 1", "linha 2"]
    assert detalhe["proximo_offset"] == 2

    # Polling incremental: a tela só pede o que ainda não tem.
    seguinte = client.get(
        f"/api/admin/datasets/tarefas/{criada['id']}?desde={detalhe['proximo_offset']}"
    ).json()
    assert seguinte["linhas"] == []
    assert seguinte["proximo_offset"] == 2


@pytest.mark.asyncio
async def test_nao_dispara_duas_tarefas_do_mesmo_tipo(datasets_client, monkeypatch):
    # Duas ingestões simultâneas escreveriam na mesma collection; dois
    # benchmarks disputariam a mesma GPU.
    client = _sem_auth(datasets_client)
    admin_datasets._tarefas.clear()

    async def _travada(tarefa, raiz):
        tarefa.estado = "rodando"

    monkeypatch.setattr(admin_datasets, "_acompanhar", _travada)

    assert client.post("/api/admin/datasets/tarefas", json={"tipo": "triagem"}).status_code == 200
    assert client.post("/api/admin/datasets/tarefas", json={"tipo": "triagem"}).status_code == 409
    # Tipo diferente pode rodar em paralelo.
    assert (
        client.post("/api/admin/datasets/tarefas", json={"tipo": "ingerir_corpus"}).status_code
        == 200
    )


def test_gerar_rascunho_recusa_quando_ha_item_revisado(datasets_client):
    # No fixture o roteador tem 1 item aprovado: regerar apagaria a revisão.
    client = _sem_auth(datasets_client)

    resposta = client.post("/api/admin/datasets/tarefas", json={"tipo": "gerar_rascunho_roteador"})

    assert resposta.status_code == 409
    assert "revisados" in resposta.json()["detail"]
