"""Schemas Pydantic para a autenticação mockada (Fase 7).

# MVP: autenticação simplificada com senha fixa padrão (12345),
# vinculada à base de clientes fictícia (ver docs/ARCHITECTURE.md §5).
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Requisição de login."""

    email: str = Field(..., description="E-mail do usuário.")
    password: str = Field(..., description="Senha do usuário (senha mock: 12345).")


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
