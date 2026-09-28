"""Schemas Pydantic para a API REST pública de Pedidos, Cotação e Frete (R12, Fase 7).

Usados por `app.api.orders` para receber requisições de criação de pedidos,
cotações/simulações B2C/B2B e cálculo de frete a partir do site ou chat.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class OrderItemIn(BaseModel):
    produto_id: int
    quantidade: int = Field(gt=0)
    centro_distribuicao: str = Field(min_length=1)


class OrderCreateIn(BaseModel):
    user_email: str | None = None
    conversation_id: str | None = None
    itens: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    id: UUID | None = None
    produto_id: int
    nome_produto: str | None = None
    quantidade: int
    centro_distribuicao: str
    preco_unitario: Decimal
    subtotal: Decimal

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: UUID
    status: str
    criado_em: datetime
    user_email: str | None = None
    conversation_id: str | None = None
    itens: list[OrderItemOut]
    valor_total: Decimal

    model_config = {"from_attributes": True}


class OrdersListOut(BaseModel):
    items: list[OrderOut]
    total: int
    limit: int
    offset: int


class FreightQuoteIn(BaseModel):
    cep: str = Field(min_length=8, max_length=9)
    itens: list[OrderItemIn] = Field(min_length=1)


class FreightQuoteOut(BaseModel):
    cep: str
    peso_total_kg: Decimal
    custo_estimado: Decimal
    prazo_dias: int


class OrderSimulationIn(BaseModel):
    itens: list[OrderItemIn] = Field(min_length=1)


class OrderSimulationItemOut(BaseModel):
    produto_id: int
    nome_produto: str | None = None
    quantidade: int
    preco_unitario_base: Decimal
    percentual_desconto_aplicado: Decimal
    subtotal: Decimal


class OrderSimulationOut(BaseModel):
    itens: list[OrderSimulationItemOut]
    valor_total: Decimal
