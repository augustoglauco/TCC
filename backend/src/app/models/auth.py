"""Schemas Pydantic para a autenticação mockada (Fase 7).

# MVP: autenticação simplificada com senha fixa padrão (12345),
# vinculada à base de clientes fictícia (ver docs/ARCHITECTURE.md §5).
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Requisição de login."""

    email: str = Field(..., description="E-mail do usuário.")
    password: str = Field(..., description="Senha do usuário (senha mock: 12345).")


class RegisterRequest(BaseModel):
    """Requisição de novo cadastro de usuário."""

    nome: str = Field(..., description="Nome completo do usuário.")
    email: str = Field(..., description="E-mail do usuário.")
    password: str = Field(default="12345", description="Senha do usuário (senha mock: 12345).")
    perfil: str = Field(default="Cliente", description="Perfil do usuário: Cliente ou Admin.")
    requester_email: str | None = Field(
        default=None, description="E-mail do usuário autenticado que está realizando o cadastro."
    )


class UserOut(BaseModel):
    """Dados públicos do usuário autenticado."""

    id: int
    email: str
    nome: str
    perfil: str = Field(
        ...,
        description=(
            "Classificação comercial do usuário: cliente, esporadico, lead ou nao_classificado."
        ),
    )
    perfil_motivo: str | None = None


class LoginResponse(BaseModel):
    """Resposta com token mock e dados do usuário."""

    token: str
    user: UserOut
