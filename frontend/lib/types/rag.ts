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
