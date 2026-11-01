"""Registro das ferramentas de escrita do Admin no chat."""

from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession


class PropostaInvalidaError(Exception):
    """Proposta inexistente, de outro admin, expirada, já resolvida ou com argumentos inválidos."""


class Previa(BaseModel):
    titulo: str
    antes: dict[str, Any]
    depois: dict[str, Any]
    aviso: str | None = None


class Ferramenta(Protocol):
    nome: str

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa: ...

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]: ...


def validar_args(modelo: type[BaseModel], args: dict[str, Any]) -> Any:
    try:
        return modelo(**args)
    except ValidationError as exc:
        campo = exc.errors()[0]["loc"][0] if exc.errors() else "argumentos"
        raise PropostaInvalidaError(f"Argumento inválido: {campo}.") from exc


# Preenchido pelas ferramentas (Tasks 3–5) ao final de cada módulo de ferramenta.
FERRAMENTAS: dict[str, Ferramenta] = {}


# Importados ao final para registrar as ferramentas em FERRAMENTAS (evita ciclo de import).
from app.admin_tools import (  # noqa: E402, F401
    ferramentas_estoque,
    ferramentas_produto,
    ferramentas_venda,
)
