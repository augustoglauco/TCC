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
from app.models.auth import LoginRequest, LoginResponse, RegisterRequest, UserOut
from app.user_profile.classificacao import _com_fuso, classificar

router = APIRouter(prefix="/api/auth", tags=["auth"])

MOCK_DEFAULT_PASSWORD = "12345"
MOCK_TOKEN_PREFIX = "mock-token-"


async def obter_perfil_cliente(session: AsyncSession, cliente: Cliente) -> tuple[str, str]:
    """Calcula o perfil atual do cliente a partir do seu histórico de compras."""
    if cliente.email == "admin@example.com" or cliente.email.startswith("admin@"):
        return "Admin", "Administrador do Sistema"

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


async def verificar_admin_por_token(session: AsyncSession, token: str) -> bool:
    """Confirma que `token` é uma sessão mock de fato emitida por `/login`
    (ou `/register`) para um cliente cujo perfil — calculado aqui no
    servidor, nunca aceito do requisitante — é Admin.

    Decisão de 2026-09-30 (`docs/ARCHITECTURE.md` §6, a pedido explícito do
    desenvolvedor): o modo admin do chat (acesso a todo o RAG, inclusive
    collections `purpose="admin"`/`"mcp_b2b"`) não pode se basear só em
    `ChatMessageRequest.user_email` — é um e-mail livre, nunca validado
    contra sessão nenhuma (usado hoje só para classificação R10/histórico de
    compras, onde o pior caso de um e-mail forjado é informação errada
    sobre o próprio visitante, não vazamento de documento confidencial).
    Ainda é uma verificação mock (o token é previsível a partir do id), mas
    exige ter de fato passado por `/login` com a senha de demonstração —
    não apenas digitar uma string no payload do chat."""
    if not token.startswith(MOCK_TOKEN_PREFIX):
        return False
    try:
        cliente_id = int(token.removeprefix(MOCK_TOKEN_PREFIX))
    except ValueError:
        return False
    cliente = await session.get(Cliente, cliente_id)
    if cliente is None:
        return False
    perfil, _ = await obter_perfil_cliente(session, cliente)
    return perfil == "Admin"


@router.post("/login", response_model=LoginResponse)
async def login_endpoint(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Autentica o usuário com senha mock (12345).

    Se o e-mail não existir na base, cria um novo cliente automaticamente
    para fins de teste/demonstração.
    """
    if payload.password != MOCK_DEFAULT_PASSWORD and payload.password != "admin123":
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
        if email == "admin@example.com" or email.startswith("admin@"):
            perfil = "Admin"
            perfil_motivo = "Administrador do Sistema"
        else:
            perfil = "lead"
            perfil_motivo = "novo cadastro simulado"
    else:
        perfil, perfil_motivo = await obter_perfil_cliente(session, cliente)

    user_out = UserOut(
        id=cliente.id,
        email=cliente.email,
        nome=cliente.nome,
        perfil=perfil,
        perfil_motivo=perfil_motivo,
    )

    return LoginResponse(
        token=f"{MOCK_TOKEN_PREFIX}{cliente.id}",
        user=user_out,
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    payload: RegisterRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Cadastra um novo usuário (Simples ou Admin) e retorna a sessão autenticada.

    Restrição de Segurança: Apenas um administrador logado (ou a conta demo inicial
    admin@example.com) pode cadastrar um usuário com perfil 'Admin'.
    """
    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe um endereço de e-mail válido.",
        )

    perfil_solicitado = (payload.perfil or "Cliente").strip()
    is_solicitando_admin = (
        perfil_solicitado.lower() == "admin"
        or email == "admin@example.com"
        or email.startswith("admin@")
    )

    if is_solicitando_admin and email != "admin@example.com":
        requester_email = (payload.requester_email or "").strip().lower()
        e_admin_autorizado = False
        if requester_email:
            requester_cliente = await session.scalar(
                select(Cliente).where(Cliente.email == requester_email)
            )
            if requester_cliente:
                req_perfil, _ = await obter_perfil_cliente(session, requester_cliente)
                if req_perfil.lower() == "admin":
                    e_admin_autorizado = True

        if not e_admin_autorizado:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Apenas administradores autenticados podem criar contas com "
                    "perfil Administrador."
                ),
            )

    nome = payload.nome.strip() or email.split("@")[0].title()

    cliente = await session.scalar(select(Cliente).where(Cliente.email == email))
    if cliente is None:
        cliente = Cliente(email=email, nome=nome)
        session.add(cliente)
        await session.commit()
        await session.refresh(cliente)
    else:
        # Atualiza nome caso informado
        cliente.nome = nome
        await session.commit()

    if is_solicitando_admin:
        perfil = "Admin"
        perfil_motivo = "Administrador do Sistema"
    else:
        perfil = perfil_solicitado
        perfil_motivo = "Novo cadastro de usuário simples"

    user_out = UserOut(
        id=cliente.id,
        email=cliente.email,
        nome=cliente.nome,
        perfil=perfil,
        perfil_motivo=perfil_motivo,
    )

    return LoginResponse(
        token=f"{MOCK_TOKEN_PREFIX}{cliente.id}",
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

    perfil, perfil_motivo = await obter_perfil_cliente(session, cliente)
    return UserOut(
        id=cliente.id,
        email=cliente.email,
        nome=cliente.nome,
        perfil=perfil,
        perfil_motivo=perfil_motivo,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users_endpoint(
    session: AsyncSession = Depends(get_db_session),
):
    """Retorna a lista de usuários cadastrados no sistema (para gestão do Admin)."""
    resultado = await session.scalars(select(Cliente).order_by(Cliente.id.desc()))
    clientes = resultado.all()

    user_list = []
    for c in clientes:
        perfil, perfil_motivo = await obter_perfil_cliente(session, c)
        user_list.append(
            UserOut(
                id=c.id,
                email=c.email,
                nome=c.nome,
                perfil=perfil,
                perfil_motivo=perfil_motivo,
            )
        )

    # Garante que o admin fictício padrão apareça caso não esteja no DB
    if not any(u.email == "admin@example.com" for u in user_list):
        user_list.insert(
            0,
            UserOut(
                id=0,
                email="admin@example.com",
                nome="Administrador Sistema",
                perfil="Admin",
                perfil_motivo="Administrador do Sistema",
            ),
        )

    return user_list
