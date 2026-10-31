"""Indicador de vida do agente de estoque (R13): cada avaliação deixa uma linha em
`agente_execucoes`, mesmo sem alerta, e `GET /api/admin/agentes/estoque/status`
resume modo, última avaliação e último alerta para o catálogo de produtos."""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agents.estoque_preditivo import avaliar_estoque
from app.agents.runtime import runtime
from app.api.admin_estoque_agente import router as status_router
from app.api.rag_dependencies import get_db_session
from app.db.catalog import atualizar_estoque, criar_pedido, criar_produto
from app.db.models import AgenteExecucao


async def _produto(session, estoque: int, nome="Gerador GD-15"):
    p = await criar_produto(
        session, nome=nome, descricao="x", preco=Decimal("100.00"), categoria="geradores"
    )
    await atualizar_estoque(session, p.id, "CD-SP", estoque)
    return p


async def _execucoes(session):
    return (await session.scalars(select(AgenteExecucao).order_by(AgenteExecucao.criado_em))).all()


async def test_avaliacao_sem_alerta_tambem_deixa_registro(db_session):
    produto = await _produto(db_session, 1000)

    await criar_pedido(db_session, [(produto.id, 5, "CD-SP")])

    [execucao] = await _execucoes(db_session)
    assert execucao.agente == "estoque"
    assert execucao.modo == "deterministico"
    assert execucao.produtos_avaliados == 1
    assert execucao.alertas_criados == 0
    assert execucao.erro is None


async def test_avaliacao_com_alerta_conta_o_alerta(db_session):
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    [execucao] = await _execucoes(db_session)
    assert execucao.alertas_criados == 1


async def test_modo_desativado_nao_registra_execucao(db_session):
    runtime.estoque_modo = "desativado"
    produto = await _produto(db_session, 10)

    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    assert await _execucoes(db_session) == []


async def test_falha_na_avaliacao_fica_registrada_com_o_erro(db_session, monkeypatch):
    produto = await _produto(db_session, 10)

    async def _explode(*_a, **_k):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr("app.agents.estoque_preditivo.coletar_fatos", _explode)

    with pytest.raises(RuntimeError):
        await avaliar_estoque(db_session, [produto.id])

    [execucao] = await _execucoes(db_session)
    assert "banco fora do ar" in execucao.erro
    assert execucao.produtos_avaliados == 0


@pytest.fixture
def status_client(db_session):
    app = FastAPI()
    app.include_router(status_router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    with TestClient(app) as c:
        yield c


async def test_status_requer_admin(status_client):
    assert status_client.get("/api/admin/agentes/estoque/status").status_code == 403


async def test_status_sem_nenhuma_avaliacao(status_client, admin_headers):
    corpo = status_client.get("/api/admin/agentes/estoque/status", headers=admin_headers).json()

    assert corpo["modo"] == "deterministico"
    assert corpo["ultima_execucao"] is None
    assert corpo["ultimo_alerta_em"] is None


async def test_status_reflete_modo_ultima_execucao_e_ultimo_alerta(
    status_client, admin_headers, db_session
):
    produto = await _produto(db_session, 10)
    await criar_pedido(db_session, [(produto.id, 8, "CD-SP")])

    corpo = status_client.get("/api/admin/agentes/estoque/status", headers=admin_headers).json()

    assert corpo["modo"] == "deterministico"
    assert corpo["ultima_execucao"]["produtos_avaliados"] == 1
    assert corpo["ultima_execucao"]["alertas_criados"] == 1
    assert corpo["ultima_execucao"]["erro"] is None
    assert corpo["ultimo_alerta_em"] is not None


async def test_status_modo_desativado(status_client, admin_headers):
    runtime.estoque_modo = "desativado"

    corpo = status_client.get("/api/admin/agentes/estoque/status", headers=admin_headers).json()

    assert corpo["modo"] == "desativado"


async def test_status_mostra_erro_da_ultima_execucao(status_client, admin_headers, db_session):
    produto = await _produto(db_session, 10)

    async def _explode(*_a, **_k):
        raise RuntimeError("falhou de propósito")

    import app.agents.estoque_preditivo as modulo

    original = modulo.coletar_fatos
    modulo.coletar_fatos = _explode
    try:
        with pytest.raises(RuntimeError):
            await avaliar_estoque(db_session, [produto.id])
    finally:
        modulo.coletar_fatos = original

    corpo = status_client.get("/api/admin/agentes/estoque/status", headers=admin_headers).json()

    assert "falhou de propósito" in corpo["ultima_execucao"]["erro"]
