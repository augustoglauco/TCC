"""Chaves de acesso ao MCP B2B pelo Admin (R12, decisão de 2026-11-05).

POST   /api/admin/parceiros-b2b/{cliente_id}/chave — gera (revoga as anteriores)
DELETE /api/admin/parceiros-b2b/{cliente_id}/chave — revoga; o texto da chave só aparece na geração
GET    /api/admin/parceiros-b2b                    — chaves ativas (só o prefixo, nunca o texto)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_auth import require_admin
from app.api.rag_dependencies import get_db_session
from app.db.models import Cliente
from app.services.chaves_parceiro import gerar_chave, listar_chaves_ativas, revogar_chaves

router = APIRouter(
    prefix="/api/admin/parceiros-b2b",
    tags=["admin-parceiros-b2b"],
    dependencies=[Depends(require_admin)],
)


class ChaveAtivaOut(BaseModel):
    cliente_id: int
    email: str
    nome: str
    prefixo: str
    criada_em: datetime


class ChaveGeradaOut(BaseModel):
    cliente_id: int
    email: str
    prefixo: str
    chave: str


@router.get("", response_model=list[ChaveAtivaOut])
async def listar_parceiros(session: AsyncSession = Depends(get_db_session)):
    return [
        ChaveAtivaOut(
            cliente_id=cliente.id,
            email=cliente.email,
            nome=cliente.nome,
            prefixo=chave.prefixo,
            criada_em=chave.criada_em,
        )
        for chave, cliente in await listar_chaves_ativas(session)
    ]


@router.post(
    "/{cliente_id}/chave", response_model=ChaveGeradaOut, status_code=status.HTTP_201_CREATED
)
async def gerar_chave_do_parceiro(cliente_id: int, session: AsyncSession = Depends(get_db_session)):
    cliente = await session.get(Cliente, cliente_id)
    if cliente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    chave, registro = await gerar_chave(session, cliente)
    return ChaveGeradaOut(
        cliente_id=cliente.id, email=cliente.email, prefixo=registro.prefixo, chave=chave
    )


@router.delete("/{cliente_id}/chave", status_code=status.HTTP_204_NO_CONTENT)
async def revogar_chave_do_parceiro(
    cliente_id: int, session: AsyncSession = Depends(get_db_session)
):
    if await revogar_chaves(session, cliente_id) == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente sem chave ativa.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
