"""Ferramentas de produto do Admin no chat: incluir, alterar nome, alterar descrição."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_tools.ferramentas import FERRAMENTAS, Previa, PropostaInvalidaError
from app.db.catalog import atualizar_produto, criar_produto, listar_produtos, obter_produto
from app.db.models import Produto


class ProdutoAmbiguoError(PropostaInvalidaError):
    def __init__(self, candidatos: list[tuple[int, str]]):
        self.candidatos = candidatos
        lista = "; ".join(f"{i}: {n}" for i, n in candidatos)
        super().__init__(f"Mais de um produto combina ({lista}). Informe o id.")


async def resolver_produto(session: AsyncSession, referencia: str | int) -> Produto:
    """Produto por id ou por nome; nunca escolhe sozinho entre vários."""
    texto = str(referencia).strip()
    if isinstance(referencia, int) or (texto.isascii() and texto.isdigit()):
        produto = await obter_produto(session, int(referencia))
        if produto is None:
            raise PropostaInvalidaError(f"Produto {referencia} não encontrado.")
        return produto
    achados = await listar_produtos(session, termo=str(referencia))
    if not achados:
        raise PropostaInvalidaError(f"Nenhum produto combina com '{referencia}'.")
    if len(achados) > 1:
        raise ProdutoAmbiguoError([(p.id, p.nome) for p in achados[:10]])
    return achados[0]


def _validar(modelo: type[BaseModel], args: dict[str, Any]) -> Any:
    try:
        return modelo(**args)
    except ValidationError as exc:
        campo = exc.errors()[0]["loc"][0] if exc.errors() else "argumentos"
        raise PropostaInvalidaError(f"Argumento inválido: {campo}.") from exc


def _preco_decimal(v: Any) -> Any:
    """Aceita "199,90" e "1.299,90" (formato brasileiro) além de "199.90"."""
    if isinstance(v, str) and "," in v:
        return v.strip().replace(".", "").replace(",", ".")
    return v


def _texto_nao_vazio(v: str) -> str:
    if not v.strip():
        raise ValueError("vazio")
    return v.strip()


class _Incluir(BaseModel):
    nome: str = Field(min_length=1)
    descricao: str = Field(min_length=1)
    preco: Decimal = Field(gt=0)
    categoria: str = Field(min_length=1)

    _limpa = field_validator("nome", "descricao", "categoria")(_texto_nao_vazio)
    _preco = field_validator("preco", mode="before")(_preco_decimal)


class _AlterarNome(BaseModel):
    produto: str | int
    novo_nome: str = Field(min_length=1)

    _limpa = field_validator("novo_nome")(_texto_nao_vazio)


class _AlterarDescricao(BaseModel):
    produto: str | int
    nova_descricao: str = Field(min_length=1)

    _limpa = field_validator("nova_descricao")(_texto_nao_vazio)


class IncluirProduto:
    nome = "incluir_produto"

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(_Incluir, args)
        return Previa(
            titulo="Incluir produto",
            antes={},
            depois={
                "nome": dados.nome,
                "descricao": dados.descricao,
                "categoria": dados.categoria,
                "preco": str(dados.preco),
            },
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(_Incluir, args)
        produto = await criar_produto(
            session,
            nome=dados.nome,
            descricao=dados.descricao,
            preco=dados.preco,
            categoria=dados.categoria,
            commit=False,
        )
        return {"produto_id": produto.id, "nome": produto.nome}


class _AlterarCampo:
    """Base das alterações de um único campo de texto do produto."""

    nome: str
    campo: str
    modelo: type[BaseModel]
    arg_novo: str
    titulo: str

    async def preparar(self, session: AsyncSession, args: dict[str, Any]) -> Previa:
        dados = _validar(self.modelo, args)
        produto = await resolver_produto(session, dados.produto)
        return Previa(
            titulo=f"{self.titulo}: {produto.nome}",
            antes={self.campo: getattr(produto, self.campo)},
            depois={self.campo: getattr(dados, self.arg_novo)},
        )

    async def executar(
        self, session: AsyncSession, args: dict[str, Any], *, admin_id: int
    ) -> dict[str, Any]:
        dados = _validar(self.modelo, args)
        produto = await resolver_produto(session, dados.produto)
        novo = getattr(dados, self.arg_novo)
        await atualizar_produto(session, produto.id, {self.campo: novo}, commit=False)
        return {self.campo: novo}


class AlterarNomeProduto(_AlterarCampo):
    nome = "alterar_nome_produto"
    campo, modelo, arg_novo, titulo = "nome", _AlterarNome, "novo_nome", "Alterar nome"


class AlterarDescricaoProduto(_AlterarCampo):
    nome = "alterar_descricao_produto"
    campo, modelo, arg_novo, titulo = (
        "descricao",
        _AlterarDescricao,
        "nova_descricao",
        "Alterar descrição",
    )


for _f in (IncluirProduto(), AlterarNomeProduto(), AlterarDescricaoProduto()):
    FERRAMENTAS[_f.nome] = _f
