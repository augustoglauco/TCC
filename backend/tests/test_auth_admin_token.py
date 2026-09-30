"""Testes de `app.api.auth.verificar_admin_por_token` (decisão de
2026-09-30, docs/ARCHITECTURE.md §6): o modo admin do chat (RAG completo)
exige um token de fato emitido por `/login`/`/register` para um cliente cujo
perfil, calculado no servidor, é Admin — não um `user_email` livre.
"""

from app.api.auth import MOCK_TOKEN_PREFIX, verificar_admin_por_token
from app.db.models import Cliente


async def test_verificar_admin_por_token_admin_valido(db_session):
    cliente = Cliente(email="admin@example.com", nome="Admin")
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)

    assert await verificar_admin_por_token(db_session, f"{MOCK_TOKEN_PREFIX}{cliente.id}") is True


async def test_verificar_admin_por_token_cliente_comum_e_falso(db_session):
    cliente = Cliente(email="visitante@example.com", nome="Visitante")
    db_session.add(cliente)
    await db_session.commit()
    await db_session.refresh(cliente)

    assert await verificar_admin_por_token(db_session, f"{MOCK_TOKEN_PREFIX}{cliente.id}") is False


async def test_verificar_admin_por_token_formato_invalido_e_falso(db_session):
    assert await verificar_admin_por_token(db_session, "qualquer-coisa") is False
    assert await verificar_admin_por_token(db_session, "") is False
    assert await verificar_admin_por_token(db_session, f"{MOCK_TOKEN_PREFIX}nao-e-um-id") is False


async def test_verificar_admin_por_token_cliente_inexistente_e_falso(db_session):
    assert await verificar_admin_por_token(db_session, f"{MOCK_TOKEN_PREFIX}999999") is False
