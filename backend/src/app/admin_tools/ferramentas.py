"""Registro das ferramentas de escrita do Admin no chat."""

from typing import Any, Protocol

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


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


# Preenchido pelas ferramentas (Tasks 3–5) ao final de cada módulo de ferramenta.
FERRAMENTAS: dict[str, Ferramenta] = {}
