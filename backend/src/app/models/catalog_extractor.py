from pydantic import BaseModel, Field
from app.models.catalog import ProdutoOut


class ExtractedProduct(BaseModel):
    """Produto extraído de página ou imagem de catálogo."""
    nome: str
    descricao: str = ""
    categoria: str = ""
    preco_base_fornecedor: float | None = None
    preco: float | None = None
    especificacoes_tecnicas: str | None = None
    imagem_temp_url: str | None = None
    pagina_origem: int = 1
    confianca: float = 1.0
    provider_usado: str = "local"


class CatalogPageResult(BaseModel):
    """Resultado processado de uma única página ou imagem."""
    pagina: int
    total_paginas: int
    produtos: list[ExtractedProduct] = Field(default_factory=list)
    provider_usado: str
    imagem_preview_url: str | None = None


class CatalogConfirmItem(BaseModel):
    """Item a ser persistido na confirmação."""
    nome: str
    descricao: str = ""
    categoria: str = ""
    preco_base_fornecedor: float | None = None
    preco: float | None = None
    especificacoes_tecnicas: str | None = None
    imagem_temp_url: str | None = None


class CatalogConfirmRequest(BaseModel):
    """Lote de produtos aprovados pelo administrador na tabela de conferência."""
    produtos: list[CatalogConfirmItem]


class CatalogConfirmResponse(BaseModel):
    """Resultado da gravação definitiva no banco e catálogo visual CLIP."""
    criados: int
    produtos: list[ProdutoOut]
