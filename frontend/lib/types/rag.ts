/**
 * Tipos do contrato de `POST /api/rag/documents` (ver `docs/FRONTEND.md` §4 e
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

export type RagDocumentOrigin = "upload" | "batch_script";

/** Um item de `GET /api/rag/documents` (ver `backend/src/app/models/rag.py`). */
export interface DocumentRegistryEntry {
  id: string;
  filename: string;
  domain: RagDomain;
  chunk_count: number;
  embedding_model: string;
  chunk_size: number;
  chunk_overlap: number;
  origin: RagDocumentOrigin;
  created_at: string;
}
