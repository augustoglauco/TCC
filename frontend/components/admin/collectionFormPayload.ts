import { CURATED_MODELS } from "./CollectionEmbeddingSection";
import type {
  CollectionCreatePayload,
  CollectionPurpose,
  PayloadIndex,
  QuantizationType,
  TextIndexParams,
} from "@/lib/types/rag";

export const PAYLOAD_INDEXES_PADRAO: PayloadIndex[] = [
  { field: "domain", schema_type: "keyword" },
  { field: "document_id", schema_type: "keyword" },
];

const TEXT_PARAMS_PADRAO: TextIndexParams = {
  tokenizer: "word",
  min_token_len: null,
  max_token_len: null,
  lowercase: true,
};

export interface CollectionFormValores {
  name: string;
  purpose: CollectionPurpose;
  modelSelecionado: string;
  modeloCustom: string;
  distanceMetric: CollectionCreatePayload["distance_metric"];
  chunkSize: number;
  chunkOverlap: number;
  hnswM: number;
  hnswEfConstruct: number;
  hnswFullScanThreshold: number;
  hnswMaxIndexingThreads: number;
  hnswOnDisk: boolean;
  hnswPayloadM: string;
  quantizationType: QuantizationType;
  scalarQuantile: number;
  scalarAlwaysRam: boolean;
  productCompression: "x4" | "x8" | "x16" | "x32" | "x64";
  productAlwaysRam: boolean;
  binaryAlwaysRam: boolean;
  payloadIndexes: PayloadIndex[];
  ativarAposCriar: boolean;
}

export const VALORES_INICIAIS: CollectionFormValores = {
  name: "",
  purpose: "chat",
  modelSelecionado: CURATED_MODELS[0].value,
  modeloCustom: "",
  distanceMetric: "cosine",
  chunkSize: 800,
  chunkOverlap: 100,
  hnswM: 16,
  hnswEfConstruct: 100,
  hnswFullScanThreshold: 10000,
  hnswMaxIndexingThreads: 0,
  hnswOnDisk: false,
  hnswPayloadM: "",
  quantizationType: "none",
  scalarQuantile: 0.99,
  scalarAlwaysRam: false,
  productCompression: "x16",
  productAlwaysRam: false,
  binaryAlwaysRam: false,
  payloadIndexes: PAYLOAD_INDEXES_PADRAO,
  ativarAposCriar: false,
};

export function modeloDeEmbedding(v: CollectionFormValores): string {
  return v.modelSelecionado === "__custom__" ? v.modeloCustom : v.modelSelecionado;
}

export function chunkingInvalido(v: CollectionFormValores): boolean {
  return v.chunkSize <= v.chunkOverlap;
}

function montarQuantization(v: CollectionFormValores): CollectionCreatePayload["quantization"] {
  const tipo = v.quantizationType;
  return {
    type: tipo,
    scalar:
      tipo === "scalar" ? { quantile: v.scalarQuantile, always_ram: v.scalarAlwaysRam } : null,
    product:
      tipo === "product"
        ? { compression: v.productCompression, always_ram: v.productAlwaysRam }
        : null,
    binary: tipo === "binary" ? { always_ram: v.binaryAlwaysRam } : null,
  };
}

function montarPayloadIndexes(indexes: PayloadIndex[]): CollectionCreatePayload["payload_indexes"] {
  return indexes
    .filter((item) => item.field.trim() !== "")
    .map((item) =>
      item.schema_type === "text"
        ? {
            field: item.field,
            schema_type: item.schema_type,
            text_params: item.text_params ?? TEXT_PARAMS_PADRAO,
          }
        : { field: item.field, schema_type: item.schema_type },
    );
}

export function montarPayload(v: CollectionFormValores): CollectionCreatePayload {
  return {
    name: v.name,
    embedding_model: modeloDeEmbedding(v),
    distance_metric: v.distanceMetric,
    chunk_size: v.chunkSize,
    chunk_overlap: v.chunkOverlap,
    hnsw: {
      m: v.hnswM,
      ef_construct: v.hnswEfConstruct,
      full_scan_threshold: v.hnswFullScanThreshold,
      max_indexing_threads: v.hnswMaxIndexingThreads,
      on_disk: v.hnswOnDisk,
      payload_m: v.hnswPayloadM === "" ? null : Number(v.hnswPayloadM),
    },
    quantization: montarQuantization(v),
    payload_indexes: montarPayloadIndexes(v.payloadIndexes),
    purpose: v.purpose,
  };
}
