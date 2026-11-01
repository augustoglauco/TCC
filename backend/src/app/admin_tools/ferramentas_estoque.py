"""Ferramenta de baixa de estoque do Admin no chat."""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa, PropostaInvalidaError
from app.admin_tools.ferramentas_produto import _validar, resolver_produto
from app.db.catalog import EstoqueInsuficienteError, baixar_estoque_atomico
from app.db.models import ProdutoEstoque


class _Baixa(BaseModel):
    produto: str | int
    cd: str = Field(min_length=1)
    quantidade: int = Field(gt=0)


async def _saldo(session: AsyncSession, produto_id: int, cd: str) -> int | None:
    """Saldo lido do banco (não da relação carregada, que pode estar velha na sessão)."""
    resultado = await session.execute(
        select(ProdutoEstoque.quantidade).where(
            ProdutoEstoque.produto_id == produto_id,
            ProdutoEstoque.centro_distribuicao == cd,
        )
    )
    return resultado.scalar_one_or_none()


class BaixaEstoque:
    nome = "baixa_estoque"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(_Baixa, args)
        produto = await resolver_produto(session, dados.produto)
        saldo = await _saldo(session, produto.id, dados.cd)
        if saldo is None:
            raise PropostaInvalidaError(f"{produto.nome} não tem estoque em {dados.cd}.")
        if saldo < dados.quantidade:
            raise PropostaInvalidaError(
                f"Estoque insuficiente em {dados.cd}: saldo {saldo}, "
                f"baixa pedida {dados.quantidade}."
            )
        return Previa(
            titulo=f"Baixa de estoque: {produto.nome}",
            antes={dados.cd: saldo},
            depois={dados.cd: saldo - dados.quantidade},
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(_Baixa, args)
        produto = await resolver_produto(session, dados.produto)
        try:
            novo = await baixar_estoque_atomico(session, produto.id, dados.cd, dados.quantidade)
        except EstoqueInsuficienteError as exc:
            raise PropostaInvalidaError(str(exc)) from exc
        return {dados.cd: novo}


FERRAMENTAS["baixa_estoque"] = BaixaEstoque()
