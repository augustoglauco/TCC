/**
 * Tipos do contrato dos endpoints do RAG (ver `docs/FRONTEND.md` §4 e
 * `backend/src/app/models/rag.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

// MVP: mesmo conjunto de domínios com RAG de texto — "agendamento" e
// "fora_escopo" não têm collection própria (ver `RagDomain` no backend).
export type RagDomain = "vendas" | "suporte" | "atendimento";

export interface DocumentIngestResponse {
  filename: string;
  domain: RagDomain;
  chunks: number;
}

export type RagDocumentOrigin = "upload" | "batch_script" | "reingest" | "crawler";

/** Um item de `GET /api/rag/documents`. */
export interface DocumentRegistryEntry {
  id: string;
  filename: string;
  domain: RagDomain;
  chunk_count: number;
  collection_id: string;
  collection_name: string;
  origin: RagDocumentOrigin;
  created_at: string;
}

export type DistanceMetric = "cosine" | "euclid" | "dot" | "manhattan";
export type QuantizationType = "none" | "scalar" | "product" | "binary";
// Finalidade da collection: "chat" (pública, buscada pelo chat) vs "mcp_b2b"
// (restrita ao canal MCP B2B, nunca ativada nem buscada pelo chat) — ver
// docs/superpowers/specs/2026-09-21-ingestao-mcp-b2b-design.md §2.
export type CollectionPurpose = "chat" | "mcp_b2b";
export type PayloadSchemaType =
  "keyword" | "integer" | "float" | "bool" | "geo" | "datetime" | "uuid" | "text";

export interface HnswConfig {
  m: number;
  ef_construct: number;
  full_scan_threshold: number;
  max_indexing_threads: number;
  on_disk: boolean;
  payload_m: number | null;
}

export interface ScalarQuantizationConfig {
  quantile: number;
  always_ram: boolean;
}

export interface ProductQuantizationConfig {
  compression: "x4" | "x8" | "x16" | "x32" | "x64";
  always_ram: boolean;
}

export interface BinaryQuantizationConfig {
  always_ram: boolean;
}

export interface QuantizationConfig {
  type: QuantizationType;
  scalar?: ScalarQuantizationConfig | null;
  product?: ProductQuantizationConfig | null;
  binary?: BinaryQuantizationConfig | null;
}

export interface TextIndexParams {
  tokenizer: "prefix" | "whitespace" | "word" | "multilingual";
  min_token_len: number | null;
  max_token_len: number | null;
  lowercase: boolean;
}

export interface PayloadIndex {
  field: string;
  schema_type: PayloadSchemaType;
  text_params?: TextIndexParams | null;
}

/** Corpo de `POST /api/rag/collections`. */
export interface CollectionCreatePayload {
  name: string;
  embedding_model: string;
  distance_metric: DistanceMetric;
  chunk_size: number;
  chunk_overlap: number;
  hnsw: HnswConfig;
  quantization: QuantizationConfig;
  payload_indexes: PayloadIndex[];
  purpose: CollectionPurpose;
}

/** Um item de `GET /api/rag/collections`. */
export interface RagCollection {
  id: string;
  name: string;
  embedding_model: string;
  vector_dimension: number;
  distance_metric: DistanceMetric;
  chunk_size: number;
  chunk_overlap: number;
  hnsw_m: number;
  hnsw_ef_construct: number;
  hnsw_full_scan_threshold: number;
  hnsw_max_indexing_threads: number;
  hnsw_on_disk: boolean;
  hnsw_payload_m: number | null;
  quantization_type: QuantizationType;
  quantization_config: Record<string, unknown>;
  payload_indexes: PayloadIndex[];
  is_active: boolean;
  purpose: CollectionPurpose;
  document_count: number;
  created_at: string;
}

export interface PlaygroundDocumentResult {
  content: string;
  source: string;
  score: number;
}

/** Um item de `PlaygroundSearchResponse.items` — resultado (ou erro) de uma collection. */
export interface PlaygroundResultItem {
  collection_id: string;
  collection_name: string;
  latency_ms?: number | null;
  results?: PlaygroundDocumentResult[];
  error?: string | null;
}

export interface PlaygroundSearchPayload {
  query: string;
  domain: RagDomain;
  collection_ids: string[];
}

export interface PlaygroundSearchResponse {
  items: PlaygroundResultItem[];
}
