"""Endpoints REST para autenticação simples e mockada de usuários (R10, Fase 7).

# MVP: senha padrão única ('12345') para ambiente de demonstração,
# associada à base de clientes fictícia (ver docs/ARCHITECTURE.md §5).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.models import Cliente, ClienteCompra
from app.models.auth import LoginRequest, LoginResponse, UserOut
from app.user_profile.classificacao import _com_fuso, classificar

router = APIRouter(prefix="/api/auth", tags=["auth"])

MOCK_DEFAULT_PASSWORD = "12345"


async def _obter_perfil_cliente(session: AsyncSession, cliente: Cliente) -> tuple[str, str]:
    """Calcula o perfil atual do cliente a partir do seu histórico de compras."""
    resultado = await session.execute(
        select(ClienteCompra.comprado_em).where(ClienteCompra.cliente_id == cliente.id)
    )
    datas_compras = [_com_fuso(data) for data in resultado.scalars().all()]
    classificacao = classificar(
        datas_compras=datas_compras,
        tem_email=True,
        teve_intencao_compra=False,
        agora=datetime.now(UTC),
    )
    return classificacao.perfil, classificacao.motivo


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Autentica o usuário com senha mock (12345).

    Se o e-mail não existir na base, cria um novo cliente automaticamente
    para fins de teste/demonstração.
    """
    if payload.password != MOCK_DEFAULT_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha de demonstração incorreta. Utilize a senha padrão: 12345.",
        )

    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe um endereço de e-mail válido.",
        )

    cliente = await session.scalar(select(Cliente).where(Cliente.email == email))
    if cliente is None:
        # Novo usuário simulado: cria cadastro na hora
        nome_sugerido = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        cliente = Cliente(email=email, nome=nome_sugerido)
        session.add(cliente)
        await session.commit()
        await session.refresh(cliente)
        perfil = "lead"
        perfil_motivo = "novo cadastro simulado"
    else:
        perfil, perfil_motivo = await _obter_perfil_cliente(session, cliente)

    user_out = UserOut(
        id=cliente.id,
        email=cliente.email,
        nome=cliente.nome,
        perfil=perfil,
        perfil_motivo=perfil_motivo,
    )

    return LoginResponse(
        token=f"mock-token-{cliente.id}",
        user=user_out,
    )


@router.get("/me", response_model=UserOut)
async def get_current_user_endpoint(
    email: str = Query(..., description="E-mail do usuário autenticado"),
    session: AsyncSession = Depends(get_db_session),
):
    """Retorna os dados do usuário autenticado a partir do e-mail."""
    email_limpo = email.strip().lower()
    cliente = await session.scalar(select(Cliente).where(Cliente.email == email_limpo))
    if cliente is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado.",
        )

    perfil, perfil_motivo = await _obter_perfil_cliente(session, cliente)
    return UserOut(
        id=cliente.id,
        email=cliente.email,
        nome=cliente.nome,
        perfil=perfil,
        perfil_motivo=perfil_motivo,
    )
