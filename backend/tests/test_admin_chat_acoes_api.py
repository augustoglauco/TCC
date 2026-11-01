import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin_tools import ferramentas
from app.admin_tools.ferramentas import Previa
from app.admin_tools.propostas import criar_proposta
from app.api.admin_chat_acoes import router
from app.api.rag_dependencies import get_db_session
from app.db.models import ChatAdminAcao


class _Fake:
    nome = "fake"

    async def preparar(self, session, args):
        return Previa(titulo="Fake", antes={}, depois={"v": 1})

    async def executar(self, session, args, *, admin_id):
        return {"v": 1}


class _Quebra(_Fake):
    async def executar(self, session, args, *, admin_id):
        raise RuntimeError("boom")


@pytest.fixture
def client(db_session, monkeypatch):
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", _Fake())
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_session] = lambda: db_session
    return TestClient(app)


def _admin_id(admin_headers) -> int:
    return int(admin_headers["Authorization"].rsplit("-", 1)[-1])


@pytest.mark.asyncio
async def test_confirmar_sem_token_admin_retorna_403(client, db_session):
    acao, _ = await criar_proposta(db_session, admin_id=1, ferramenta="fake", argumentos={})
    assert client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar").status_code == 403
    await db_session.refresh(acao)
    assert acao.status == "proposta"


@pytest.mark.asyncio
async def test_confirmar_executa_e_reconfirmar_retorna_409(client, db_session, admin_headers):
    aid = _admin_id(admin_headers)
    acao, _ = await criar_proposta(db_session, admin_id=aid, ferramenta="fake", argumentos={})
    ok = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert ok.status_code == 200 and ok.json() == {"status": "executada", "depois": {"v": 1}}
    again = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_cancelar(client, db_session, admin_headers):
    aid = _admin_id(admin_headers)
    acao, _ = await criar_proposta(db_session, admin_id=aid, ferramenta="fake", argumentos={})
    r = client.post(f"/api/admin/chat/acoes/{acao.id}/cancelar", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "cancelada"
    de_novo = client.post(f"/api/admin/chat/acoes/{acao.id}/cancelar", headers=admin_headers)
    assert de_novo.status_code == 409


@pytest.mark.asyncio
async def test_proposta_expirada_retorna_409_e_persiste_expirada(client, db_session, admin_headers):
    from datetime import UTC, datetime, timedelta

    aid = _admin_id(admin_headers)
    velho = datetime.now(UTC) - timedelta(hours=1)
    acao, _ = await criar_proposta(
        db_session, admin_id=aid, ferramenta="fake", argumentos={}, agora=velho
    )
    r = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert r.status_code == 409
    await db_session.refresh(acao)
    assert acao.status == "expirada"


@pytest.mark.asyncio
async def test_executar_que_levanta_retorna_409_sem_gravar(
    client, db_session, admin_headers, monkeypatch
):
    monkeypatch.setitem(ferramentas.FERRAMENTAS, "fake", _Quebra())
    aid = _admin_id(admin_headers)
    acao, _ = await criar_proposta(db_session, admin_id=aid, ferramenta="fake", argumentos={})
    acao_id = acao.id
    r = client.post(f"/api/admin/chat/acoes/{acao.id}/confirmar", headers=admin_headers)
    assert r.status_code == 409 and "nada foi gravado" in r.json()["detail"]
    linha = await db_session.get(ChatAdminAcao, acao_id)
    await db_session.refresh(linha)
    assert linha.status == "proposta" and linha.executado_em is None
