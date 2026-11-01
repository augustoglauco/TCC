"""Ferramenta de baixa de estoque do Admin no chat."""

from typing import Any, Self

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools import ferramentas_produto
from app.admin_tools.ferramentas import (
    FERRAMENTAS,
    Previa,
    PropostaInvalidaError,
    validar_args,
)
from app.db.catalog import (
    EstoqueInsuficienteError,
    baixar_estoque_atomico,
    definir_estoque_produtos,
)
from app.db.models import Produto, ProdutoEstoque

# MVP: lista fixa dos centros de distribuição do projeto, usada só para dar o nome canônico
# ("cd-matriz" → "CD-Matriz") quando nenhum produto tem estoque no centro ainda.
CDS_CONHECIDOS = ("CD-Matriz", "CD-SP", "CD-RJ")


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
        dados = validar_args(_Baixa, args)
        produto = await ferramentas_produto.resolver_produto(session, dados.produto)
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
        dados = validar_args(_Baixa, args)
        produto = await ferramentas_produto.resolver_produto(session, dados.produto)
        try:
            novo = await baixar_estoque_atomico(session, produto.id, dados.cd, dados.quantidade)
        except EstoqueInsuficienteError as exc:
            raise PropostaInvalidaError(str(exc)) from exc
        return {dados.cd: novo}


def _chave_cd(nome: str) -> str:
    return "".join(ch for ch in nome.casefold() if ch.isalnum())


async def _resolver_cd(session: AsyncSession, cd: str) -> str:
    """Nome canônico do centro: o que já existe no banco (ou na lista conhecida) sem diferenciar
    caixa, hífen ou espaço; se não existir em lugar nenhum, o texto informado."""
    existentes = await session.execute(select(ProdutoEstoque.centro_distribuicao).distinct())
    candidatos = [*existentes.scalars().all(), *CDS_CONHECIDOS]
    return next((c for c in candidatos if _chave_cd(c) == _chave_cd(cd)), cd.strip())


class _Ajuste(BaseModel):
    produto: str | int | None = None
    todos: bool = False
    cd: str = Field(min_length=1)
    quantidade: int = Field(ge=0)

    @model_validator(mode="after")
    def _um_alvo(self) -> Self:
        if self.todos == (self.produto is not None):
            raise ValueError("informe um produto OU todos=true, não os dois nem nenhum")
        return self


class AjustarEstoque:
    """Define a quantidade FINAL do estoque de um centro (um produto ou todos os produtos).
    Diferente de `baixa_estoque`, que subtrai de um produto."""

    nome = "ajustar_estoque"

    async def _alvos(self, session: AsyncSession, dados: _Ajuste) -> list[Produto]:
        if dados.todos:
            return list((await session.execute(select(Produto).order_by(Produto.id))).scalars())
        return [await ferramentas_produto.resolver_produto(session, dados.produto)]

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = validar_args(_Ajuste, args)
        cd = await _resolver_cd(session, dados.cd)
        alvos = await self._alvos(session, dados)
        if not alvos:
            raise PropostaInvalidaError("Não há produtos cadastrados.")
        if not dados.todos:
            saldo = await _saldo(session, alvos[0].id, cd) or 0
            return Previa(
                titulo=f"Ajuste de estoque: {alvos[0].nome}",
                antes={cd: saldo},
                depois={cd: dados.quantidade},
            )
        ids = [p.id for p in alvos]
        total = await session.execute(
            select(func.coalesce(func.sum(ProdutoEstoque.quantidade), 0)).where(
                ProdutoEstoque.produto_id.in_(ids), ProdutoEstoque.centro_distribuicao == cd
            )
        )
        return Previa(
            titulo=f"Ajuste de estoque de todos os produtos em {cd}",
            antes={"produtos afetados": len(ids), f"saldo total em {cd}": int(total.scalar_one())},
            depois={
                "quantidade em cada produto": dados.quantidade,
                f"saldo total em {cd}": dados.quantidade * len(ids),
            },
            aviso="Altera o estoque de todos os produtos deste centro.",
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = validar_args(_Ajuste, args)
        cd = await _resolver_cd(session, dados.cd)
        alvos = await self._alvos(session, dados)
        await definir_estoque_produtos(session, [p.id for p in alvos], cd, dados.quantidade)
        return {"centro": cd, "produtos": len(alvos), "quantidade": dados.quantidade}


FERRAMENTAS["baixa_estoque"] = BaixaEstoque()
FERRAMENTAS["ajustar_estoque"] = AjustarEstoque()
