"""Schemas Pydantic dos endpoints do RAG (R4, além do MVP): documentos,
collections e playground de busca comparativo.

Contrato de documentos espelhado em `docs/FRONTEND.md` §4
(`POST /api/rag/documents`). Contrato de collections/playground em
docs/superpowers/specs/2026-09-15-rag-collections-config-design.md §6.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# MVP: só os três domínios com RAG de texto (o mesmo conjunto usado por
# `app.rag.qdrant_client` para filtrar busca) — "agendamento" e "fora_escopo"
# não têm collection própria (ver `app.router.classifier.Domain`).
RagDomain = Literal["vendas", "suporte", "atendimento"]

# Fonte única de verdade para os valores de origem de um `RagDocument`
# (achado #1 da revisão final do branch do crawler): reutilizado tanto aqui
# quanto em `app.rag.crawler_ingest` para evitar o mesmo valor duplicado
# como string literal em dois lugares e divergir de novo.
RagDocumentOrigin = Literal["upload", "batch_script", "reingest", "crawler"]

DistanceMetric = Literal["cosine", "euclid", "dot", "manhattan"]
QuantizationType = Literal["none", "scalar", "product", "binary"]
# Finalidade da collection: "chat" (pública, elegível a ativa/busca do chat)
# vs "mcp_b2b" (restrita ao canal MCP B2B, nunca ativada nem buscada pelo
# chat) — ver docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §2.
CollectionPurpose = Literal["chat", "mcp_b2b"]
PayloadSchemaTypeLiteral = Literal[
    "keyword", "integer", "float", "bool", "geo", "datetime", "uuid", "text"
]


class DocumentIngestResponse(BaseModel):
    """Resposta de `POST /api/rag/documents`."""

    filename: str = Field(..., description="Nome do arquivo enviado.")
    domain: RagDomain = Field(..., description="Domínio informado no upload.")
    chunks: int = Field(..., description="Número de chunks gravados no Qdrant.")


class DocumentRegistryResponse(BaseModel):
    """Um item de `GET /api/rag/documents`."""

    id: UUID
    filename: str
    domain: RagDomain
    chunk_count: int
    collection_id: UUID
    collection_name: str
    origin: RagDocumentOrigin
    created_at: datetime


class ReingestRequest(BaseModel):
    """Corpo de `POST /api/rag/documents/{document_id}/reingest`."""

    target_collection_id: UUID


class HnswConfigRequest(BaseModel):
    m: int = 16
    ef_construct: int = 100
    full_scan_threshold: int = 10000
    max_indexing_threads: int = 0
    on_disk: bool = False
    payload_m: int | None = None


class ScalarQuantizationRequest(BaseModel):
    quantile: float = 0.99
    always_ram: bool = False


class ProductQuantizationRequest(BaseModel):
    compression: Literal["x4", "x8", "x16", "x32", "x64"] = "x16"
    always_ram: bool = False


class BinaryQuantizationRequest(BaseModel):
    always_ram: bool = False


class QuantizationRequest(BaseModel):
    type: QuantizationType = "none"
    scalar: ScalarQuantizationRequest | None = None
    product: ProductQuantizationRequest | None = None
    binary: BinaryQuantizationRequest | None = None


class TextIndexParamsRequest(BaseModel):
    tokenizer: Literal["prefix", "whitespace", "word", "multilingual"] = "word"
    min_token_len: int | None = None
    max_token_len: int | None = None
    lowercase: bool = True


class PayloadIndexRequest(BaseModel):
    field: str = Field(..., min_length=1)
    schema_type: PayloadSchemaTypeLiteral
    text_params: TextIndexParamsRequest | None = None


class CollectionCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    embedding_model: str = Field(..., min_length=1)
    distance_metric: DistanceMetric = "cosine"
    chunk_size: int = 800
    chunk_overlap: int = 100
    hnsw: HnswConfigRequest = Field(default_factory=HnswConfigRequest)
    quantization: QuantizationRequest = Field(default_factory=QuantizationRequest)
    payload_indexes: list[PayloadIndexRequest] = Field(default_factory=list)
    purpose: CollectionPurpose = "chat"

    @model_validator(mode="after")
    def _valida_chunking(self) -> CollectionCreateRequest:
        if self.chunk_size <= self.chunk_overlap:
            raise ValueError("chunk_size deve ser maior que chunk_overlap")
        return self


class CollectionResponse(BaseModel):
    id: UUID
    name: str
    embedding_model: str
    vector_dimension: int
    distance_metric: DistanceMetric
    chunk_size: int
    chunk_overlap: int
    hnsw_m: int
    hnsw_ef_construct: int
    hnsw_full_scan_threshold: int
    hnsw_max_indexing_threads: int
    hnsw_on_disk: bool
    hnsw_payload_m: int | None
    quantization_type: QuantizationType
    quantization_config: dict
    payload_indexes: list[PayloadIndexRequest]
    is_active: bool
    purpose: CollectionPurpose
    document_count: int
    created_at: datetime


class PlaygroundSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    domain: RagDomain
    collection_ids: list[UUID] = Field(..., min_length=1)


class PlaygroundDocumentResult(BaseModel):
    content: str
    source: str
    score: float


class PlaygroundResultItem(BaseModel):
    collection_id: UUID
    collection_name: str
    latency_ms: float | None = None
    results: list[PlaygroundDocumentResult] = Field(default_factory=list)
    error: str | None = None


class PlaygroundSearchResponse(BaseModel):
    items: list[PlaygroundResultItem]
