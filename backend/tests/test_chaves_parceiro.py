"""Chaves do MCP B2B geradas pelo Admin (R12, decisão de 2026-11-05)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.admin_parceiros_b2b import router
from app.api.rag_dependencies import get_db_session
from app.db.models import ChaveParceiro, Cliente
from app.mcp_server.auth import ChaveParceiroVerifier
from app.services.chaves_parceiro import gerar_chave, hash_da_chave


@pytest.fixture
def client(db_session):
    app = FastAPI()
    app.include_router(router)

    async def _sessao():
        yield db_session

    app.dependency_overrides[get_db_session] = _sessao
    return TestClient(app)


async def _cliente(db_session, email="compras@revenda.com.br"):
    cliente = Cliente(email=email, nome="Revenda")
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)
    return cliente


async def test_so_admin_gera_chave(client, db_session):
    cliente = await _cliente(db_session)
    assert client.post(f"/api/admin/parceiros-b2b/{cliente.id}/chave").status_code == 403


async def test_gerar_devolve_o_texto_uma_vez_e_guarda_so_o_hash(client, db_session, admin_headers):
    cliente = await _cliente(db_session)

    resposta = client.post(f"/api/admin/parceiros-b2b/{cliente.id}/chave", headers=admin_headers)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["chave"].startswith("b2b_") and len(corpo["chave"]) >= 40
    registro = (await db_session.execute(select(ChaveParceiro))).scalar_one()
    assert registro.chave_hash == hash_da_chave(corpo["chave"])
    assert corpo["chave"] not in {registro.chave_hash, registro.prefixo}
    listagem = client.get("/api/admin/parceiros-b2b", headers=admin_headers).json()
    assert listagem[0]["prefixo"] == corpo["prefixo"]
    assert "chave" not in listagem[0]


async def test_nova_chave_revoga_a_anterior(client, db_session, admin_headers):
    cliente = await _cliente(db_session)
    primeira, _ = await gerar_chave(db_session, cliente)
    segunda, _ = await gerar_chave(db_session, cliente)

    verificador = ChaveParceiroVerifier({})
    verificador.usar_banco(_fabrica(db_session))

    assert await verificador.verify_token(primeira) is None
    aceito = await verificador.verify_token(segunda)
    assert aceito is not None and aceito.client_id == "compras@revenda.com.br"


async def test_revogar_e_cliente_inexistente(client, db_session, admin_headers):
    cliente = await _cliente(db_session)
    chave, _ = await gerar_chave(db_session, cliente)

    assert (
        client.delete(
            f"/api/admin/parceiros-b2b/{cliente.id}/chave", headers=admin_headers
        ).status_code
        == 204
    )
    verificador = ChaveParceiroVerifier({})
    verificador.usar_banco(_fabrica(db_session))
    assert await verificador.verify_token(chave) is None
    assert (
        client.delete(
            f"/api/admin/parceiros-b2b/{cliente.id}/chave", headers=admin_headers
        ).status_code
        == 404
    )
    assert (
        client.post("/api/admin/parceiros-b2b/9999/chave", headers=admin_headers).status_code == 404
    )


async def test_chave_do_env_continua_valendo_junto_com_o_banco(db_session):
    verificador = ChaveParceiroVerifier({"chave-do-env-0123456789": "revendedor-demo"})
    verificador.usar_banco(_fabrica(db_session))

    aceito = await verificador.verify_token("chave-do-env-0123456789")
    assert aceito is not None and aceito.client_id == "revendedor-demo"
    assert await verificador.verify_token("qualquer-outra-coisa") is None


def _fabrica(db_session):
    class _F:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *_):
            return False

    return _F()
