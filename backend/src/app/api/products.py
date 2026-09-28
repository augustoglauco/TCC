"""Endpoints públicos para navegação do catálogo de produtos pelo site.

GET /api/products            — Lista paginada de produtos com busca, filtro por categoria e ordenação por estoque + nome alfabético
GET /api/products/categorias — Lista alfabética de categorias distintas
GET /api/products/{id}       — Detalhe de produto por ID
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.rag_dependencies import get_db_session
from app.db.catalog import listar_categorias_distintas, listar_produtos, obter_produto
from app.models.catalog import PaginatedProdutosOut, ProdutoOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])


def _ordenar_estoque_nome_key(produto: ProdutoOut):
    total_estoque = sum(e.quantidade for e in produto.estoques if e.quantidade > 0)
    tem_estoque = 0 if total_estoque > 0 else 1
    return (tem_estoque, produto.nome.lower())


@router.get("", response_model=PaginatedProdutosOut)
async def get_public_produtos(
    termo: Annotated[str | None, Query(description="Busca por nome, descrição ou especificações")] = None,
    categoria: Annotated[str | None, Query(description="Filtro por categoria")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: AsyncSession = Depends(get_db_session),
):
    todos = await listar_produtos(session, categoria=categoria, termo=termo)
    pydantic_items = [ProdutoOut.model_validate(p) for p in todos]
    pydantic_items.sort(key=_ordenar_estoque_nome_key)
    
    total = len(pydantic_items)
    paginados = pydantic_items[offset : offset + limit]
    
    return PaginatedProdutosOut(
        items=paginados,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/categorias", response_model=list[str])
async def get_public_categorias(
    session: AsyncSession = Depends(get_db_session),
):
    return await listar_categorias_distintas(session)


@router.get("/{produto_id}", response_model=ProdutoOut)
async def get_public_produto(
    produto_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    produto = await obter_produto(session, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return ProdutoOut.model_validate(produto)
