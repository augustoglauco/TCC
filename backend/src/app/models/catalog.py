"""Schemas Pydantic do backend único de catálogo/estoque/preços (R12, Fase
5) — ver `docs/ARCHITECTURE.md` §5/§6. Usados pelo módulo de acesso a dados
`app.db.catalog`, reaproveitável tanto pelo RAG quanto pelo futuro servidor
MCP B2B (itens seguintes desta mesma fase).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ProdutoEstoqueOut(BaseModel):
    id: UUID
    centro_distribuicao: str
    quantidade: int
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ProdutoDescontoVolumeOut(BaseModel):
    id: UUID
    quantidade_minima: int
    percentual_desconto: Decimal

    model_config = {"from_attributes": True}


class ProdutoImagemOut(BaseModel):
    id: int
    imagem_url: str
    clip_image_id: str | None = None
    is_principal: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class ProdutoOut(BaseModel):
    """Visão completa de um produto do catálogo, incluindo estoque por
    centro de distribuição e faixas de desconto por volume."""

    id: int
    nome: str
    descricao: str
    preco: Decimal
    categoria: str
    especificacoes_tecnicas: str | None
    dimensoes_cm: str | None
    peso_kg: Decimal | None
    preco_promocional: Decimal | None
    promocao_valida_ate: datetime | None
    preco_base_fornecedor: Decimal | None = None
    imagem_url: str | None = None
    estoques: list[ProdutoEstoqueOut] = []
    descontos_volume: list[ProdutoDescontoVolumeOut] = []
    imagens: list[ProdutoImagemOut] = []

    model_config = {"from_attributes": True}


class ProdutoCreate(BaseModel):
    nome: str
    descricao: str
    preco: Decimal
    categoria: str
    especificacoes_tecnicas: str | None = None
    dimensoes_cm: str | None = None
    peso_kg: Decimal | None = None
    preco_promocional: Decimal | None = None
    promocao_valida_ate: datetime | None = None
    preco_base_fornecedor: Decimal | None = None
    imagem_url: str | None = None


class ProdutoUpdate(BaseModel):
    """Atualização parcial — só os campos enviados mudam (mesmo padrão de
    `PUT /api/admin/runtime-settings`, ver `docs/ARCHITECTURE.md` §5)."""

    nome: str | None = None
    descricao: str | None = None
    preco: Decimal | None = None
    categoria: str | None = None
    especificacoes_tecnicas: str | None = None
    dimensoes_cm: str | None = None
    peso_kg: Decimal | None = None
    preco_promocional: Decimal | None = None
    promocao_valida_ate: datetime | None = None
    preco_base_fornecedor: Decimal | None = None
    imagem_url: str | None = None
