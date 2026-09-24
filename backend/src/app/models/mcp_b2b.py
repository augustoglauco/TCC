"""Schemas Pydantic dos recursos de leitura do servidor MCP B2B (R12, Fase
5) — ver `docs/ARCHITECTURE.md` §5/§6. Usados por `app.mcp_server.b2b` para
serializar as respostas dos 4 recursos (catálogo, estoque, preços, manuais)
como JSON no corpo de cada `ReadResourceResult` do protocolo MCP.

Reaproveitam `app.db.catalog`/`app.db.models` como fonte de dados (mesmo
backend único descrito na decisão de 2026-09-24 em `docs/ARCHITECTURE.md`
§5) — mas são schemas próprios, mais enxutos que `app.models.catalog`, um
por recurso, em vez de reaproveitar `ProdutoOut` (que mistura catálogo,
estoque e preço num único objeto — apropriado para o admin, não para os
quatro recursos MCP separados que R12/Seção 6 descreve).
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CatalogoProdutoOut(BaseModel):
    """Recurso 1 — catálogo: nome, descrição, categoria, especificações
    técnicas, dimensões e peso. Sem preço/estoque (recursos próprios)."""

    id: int
    nome: str
    descricao: str
    categoria: str
    especificacoes_tecnicas: str | None
    dimensoes_cm: str | None
    peso_kg: Decimal | None

    model_config = {"from_attributes": True}


class EstoqueCentroOut(BaseModel):
    """Um item de `produto_estoque` — quantidade por centro de distribuição."""

    centro_distribuicao: str
    quantidade: int
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class EstoqueProdutoOut(BaseModel):
    """Recurso 2 — estoque de um produto, por centro de distribuição."""

    produto_id: int
    centros: list[EstoqueCentroOut]


class DescontoVolumeOut(BaseModel):
    quantidade_minima: int
    percentual_desconto: Decimal

    model_config = {"from_attributes": True}


class PrecoProdutoOut(BaseModel):
    """Recurso 3 — tabela de preços de um produto: preço, promoção vigente
    (campanha) e faixas de desconto por volume."""

    produto_id: int
    preco: Decimal
    preco_promocional: Decimal | None
    promocao_valida_ate: datetime | None
    descontos_volume: list[DescontoVolumeOut]


class ManualResultadoOut(BaseModel):
    """Um trecho relevante encontrado na busca semântica de manuais
    (recurso 4) — chunk de texto de um documento ingerido numa collection
    RAG `purpose="mcp_b2b"` (ver `app.rag.collections_registry`)."""

    content: str
    source: str
    score: float
    collection: str


class ManualBuscaOut(BaseModel):
    resultados: list[ManualResultadoOut]
