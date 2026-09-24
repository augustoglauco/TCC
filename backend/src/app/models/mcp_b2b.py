"""Schemas Pydantic dos recursos e ferramentas do servidor MCP B2B (R12, Fase
5) — ver `docs/ARCHITECTURE.md` §5/§6. Usados por `app.mcp_server.b2b` para
serializar as respostas dos 4 recursos (catálogo, estoque, preços, manuais)
como JSON no corpo de cada `ReadResourceResult`, e para validar
entrada/serializar saída das 4 ferramentas transacionais (compatibilidade,
frete, cotação, reserva/pedido) do protocolo MCP.

Reaproveitam `app.db.catalog`/`app.db.models` como fonte de dados (mesmo
backend único descrito na decisão de 2026-09-24 em `docs/ARCHITECTURE.md`
§5) — mas são schemas próprios, mais enxutos que `app.models.catalog`, um
por recurso/ferramenta, em vez de reaproveitar `ProdutoOut` (que mistura
catálogo, estoque e preço num único objeto — apropriado para o admin, não
para os recursos/ferramentas MCP separados que R12/Seção 6 descrevem).
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


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


# --- Ferramenta 1: validação de compatibilidade ------------------------------


class CompatibilidadeOut(BaseModel):
    produto_id: int
    produto_relacionado_id: int
    compativel: bool


# --- Ferramenta 2: consulta de frete e prazos --------------------------------


class FreteItemIn(BaseModel):
    produto_id: int
    quantidade: int = Field(gt=0)


class FreteOut(BaseModel):
    """# MVP: estimativa determinística interna, não frete real — nenhuma
    transportadora/Correios é consultada (ver `docs/ARCHITECTURE.md` §5,
    decisão de 2026-09-24)."""

    cep: str
    peso_total_kg: Decimal
    custo_estimado: Decimal
    prazo_dias: int


# --- Ferramenta 3: cotação automática ----------------------------------------


class CotacaoItemIn(BaseModel):
    produto_id: int
    quantidade: int = Field(gt=0)


class CotacaoItemOut(BaseModel):
    produto_id: int
    quantidade: int
    preco_unitario: Decimal
    percentual_desconto_aplicado: Decimal
    subtotal: Decimal


class CotacaoOut(BaseModel):
    itens: list[CotacaoItemOut]
    total: Decimal


# --- Ferramenta 4: reserva/pedido ---------------------------------------------


class PedidoItemIn(BaseModel):
    produto_id: int
    quantidade: int = Field(gt=0)
    centro_distribuicao: str


class PedidoItemOut(BaseModel):
    produto_id: int
    quantidade: int
    centro_distribuicao: str
    preco_unitario: Decimal

    model_config = {"from_attributes": True}


class PedidoOut(BaseModel):
    """# MVP: `status` sempre `"reservado"`, sem trilha de auditoria nem
    pagamento/gateway real (ver `docs/ARCHITECTURE.md` §5/§6, decisão de
    2026-09-24)."""

    id: UUID
    status: str
    criado_em: datetime
    itens: list[PedidoItemOut]

    model_config = {"from_attributes": True}
