/**
 * Tipos do contrato dos endpoints do crawler de páginas do RAG (ver
 * `backend/src/app/models/crawler.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

import type { RagDomain } from "@/lib/types/rag";

/** Corpo de `POST /api/rag/crawler/run`. */
export interface CrawlRunPayload {
  url: string;
  depth: number;
  max_pages?: number;
}

/** Resposta de `POST /api/rag/crawler/run`. */
export interface CrawlRunResponse {
  pages_visited: number;
  auto_ingested: string[];
  queued: string[];
  errors: string[];
}

/** Um item de `GET /api/rag/crawler/pending`. */
export interface PendingPage {
  id: string;
  url: string;
  text_snippet: string;
  domain_proposed: RagDomain;
  confidence: number;
  created_at: string;
}

/** Corpo de `POST /api/rag/crawler/pending/{id}/approve`. */
export interface ApprovePendingPagePayload {
  domain: RagDomain;
}

/** Resposta de `POST /api/rag/crawler/pending/{id}/approve`. */
export interface ApprovedPageResponse {
  url: string;
  domain: RagDomain;
  chunks: number;
}
