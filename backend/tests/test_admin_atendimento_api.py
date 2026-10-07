"""Testes da API REST Administrativa para Atendimento Humano e Fila (/api/admin/atendimento)."""

import pytest
from datetime import UTC, datetime
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.rag_dependencies import get_db_session
from app.db.models import Cliente, Conversa, ConversaMensagem
from app.main import create_app


@pytest.fixture
def test_app(db_session):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db_session
    return app


@pytest.fixture
async def admin_headers(db_session):
    admin = Cliente(nome="Admin Atendimento", email="admin@empresa.com")
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return {"Authorization": f"Bearer mock-token-{admin.id}"}


@pytest.mark.asyncio
async def test_admin_atendimento_unauthorized(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/admin/atendimento/fila")
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_atendimento_fila_e_detalhes(test_app, db_session, admin_headers):
    # Setup conversas
    c1 = Conversa(
        id="conv-fila-p1",
        status="aguardando_humano",
        prioridade=1,
        motivo_escalonamento="solicitacao_cliente",
        escalado_em=datetime.now(UTC),
    )
    c2 = Conversa(
        id="conv-fila-p5",
        status="aguardando_humano",
        prioridade=5,
        motivo_escalonamento="tom_frustrado",
        escalado_em=datetime.now(UTC),
    )
    c3 = Conversa(
        id="conv-aberta",
        status="aberta",
    )
    db_session.add_all([c1, c2, c3])
    await db_session.commit()

    # Adiciona mensagem em c2
    m = ConversaMensagem(
        conversa_id="conv-fila-p5",
        papel="user",
        texto="Estou irritado, quero falar com alguém!",
    )
    db_session.add(m)
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Listar fila
        res = await client.get("/api/admin/atendimento/fila", headers=admin_headers)
        assert res.status_code == 200
        fila = res.json()
        assert len(fila) == 2
        # Prioridade 5 deve vir primeiro
        assert fila[0]["id"] == "conv-fila-p5"
        assert fila[0]["prioridade"] == 5
        assert fila[0]["motivo_escalonamento"] == "tom_frustrado"
        assert fila[1]["id"] == "conv-fila-p1"

        # 2. Obter detalhes da conversa
        res_det = await client.get("/api/admin/atendimento/conv-fila-p5", headers=admin_headers)
        assert res_det.status_code == 200
        detalhes = res_det.json()
        assert detalhes["id"] == "conv-fila-p5"
        assert len(detalhes["mensagens"]) == 1
        assert detalhes["mensagens"][0]["texto"] == "Estou irritado, quero falar com alguém!"

        # 3. Detalhes de conversa inexistente
        res_404 = await client.get("/api/admin/atendimento/nao-existe", headers=admin_headers)
        assert res_404.status_code == 404


@pytest.mark.asyncio
async def test_admin_atendimento_claim_e_conflito(test_app, db_session, admin_headers):
    c = Conversa(
        id="conv-claim-test",
        status="aguardando_humano",
        prioridade=3,
        escalado_em=datetime.now(UTC),
    )
    db_session.add(c)
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Atendente 1 assume
        claim_payload_1 = {
            "atendente_id": "op_carlos",
            "atendente_nome": "Carlos Suporte",
        }
        res1 = await client.post(
            "/api/admin/atendimento/conv-claim-test/claim",
            json=claim_payload_1,
            headers=admin_headers,
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["status"] == "em_atendimento_humano"
        assert data1["atendente_id"] == "op_carlos"

        # Achado de 2026-10-07: claim bem-sucedido grava automaticamente o
        # aviso "Um atendente irá atendê-lo agora." para o cliente.
        mensagens = (
            await db_session.execute(
                select(ConversaMensagem).where(ConversaMensagem.conversa_id == "conv-claim-test")
            )
        ).scalars().all()
        assert len(mensagens) == 1
        assert mensagens[0].papel == "atendente"
        assert mensagens[0].atendente_nome == "Carlos Suporte"
        assert mensagens[0].texto == "Um atendente irá atendê-lo agora."

        # Atendente 2 tenta assumir simultaneamente a mesma conversa -> 409 Conflict
        claim_payload_2 = {
            "atendente_id": "op_mariana",
            "atendente_nome": "Mariana Suporte",
        }
        res2 = await client.post(
            "/api/admin/atendimento/conv-claim-test/claim",
            json=claim_payload_2,
            headers=admin_headers,
        )
        assert res2.status_code == 409
        assert "já foi assumida" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_admin_atendimento_meus_chats(test_app, db_session, admin_headers):
    c = Conversa(
        id="conv-meu-chat",
        status="em_atendimento_humano",
        atendente_id="op_carlos",
        atendente_nome="Carlos Suporte",
    )
    db_session.add(c)
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/admin/atendimento/meus-chats?atendente_id=op_carlos",
            headers=admin_headers,
        )
        assert res.status_code == 200
        chats = res.json()
        assert len(chats) == 1
        assert chats[0]["id"] == "conv-meu-chat"
        assert chats[0]["atendente_nome"] == "Carlos Suporte"


@pytest.mark.asyncio
async def test_admin_atendimento_mensagem(test_app, db_session, admin_headers):
    c = Conversa(
        id="conv-msg-test",
        status="em_atendimento_humano",
        atendente_id="op_carlos",
        atendente_nome="Carlos Suporte",
    )
    db_session.add(c)
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/admin/atendimento/conv-msg-test/mensagem",
            json={"atendente_nome": "Carlos Suporte", "texto": "Olá! Sou o Carlos, como posso ajudar?"},
            headers=admin_headers,
        )
        assert res.status_code == 200
        msg_data = res.json()
        assert msg_data["papel"] == "atendente"
        assert msg_data["atendente_nome"] == "Carlos Suporte"
        assert msg_data["texto"] == "Olá! Sou o Carlos, como posso ajudar?"

        # Verifica persistência no banco
        stmt = select(ConversaMensagem).where(ConversaMensagem.conversa_id == "conv-msg-test")
        res_db = await db_session.execute(stmt)
        msg_db = res_db.scalars().first()
        assert msg_db is not None
        assert msg_db.papel == "atendente"


@pytest.mark.asyncio
async def test_admin_atendimento_close(test_app, db_session, admin_headers):
    c1 = Conversa(
        id="conv-close-devolver",
        status="em_atendimento_humano",
        atendente_id="op_carlos",
    )
    c2 = Conversa(
        id="conv-close-finalizar",
        status="em_atendimento_humano",
        atendente_id="op_carlos",
    )
    db_session.add_all([c1, c2])
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Devolver para IA
        res_dev = await client.post(
            "/api/admin/atendimento/conv-close-devolver/close",
            json={"acao": "devolver_ia"},
            headers=admin_headers,
        )
        assert res_dev.status_code == 200
        assert res_dev.json()["status"] == "aberta"

        # 2. Finalizar atendimento
        res_fin = await client.post(
            "/api/admin/atendimento/conv-close-finalizar/close",
            json={"acao": "finalizar", "motivo": "resolvido com sucesso"},
            headers=admin_headers,
        )
        assert res_fin.status_code == 200
        assert res_fin.json()["status"] == "encerrada"
