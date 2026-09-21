/**
 * Tipos do contrato dos endpoints do crawler de páginas do RAG (ver
 * `backend/src/app/models/crawler.py`). Mantidos em sincronia manual com o
 * backend nesta etapa do protótipo.
 */

import type { RagDomain } from "@/lib/types/rag";

/** Parâmetros de um crawl (query do endpoint SSE `GET /api/rag/crawler/run/stream`). */
export interface CrawlRunPayload {
  url: string;
  depth: number;
  max_pages?: number;
}

/** Resumo final de um crawl (evento `done` do SSE `GET /api/rag/crawler/run/stream`). */
export interface CrawlRunResponse {
  pages_visited: number;
  auto_ingested: string[];
  queued: string[];
  errors: string[];
}

/**
 * Callbacks do stream SSE de `GET /api/rag/crawler/run/stream` — progresso
 * em tempo real, um evento por página, para o frontend saber que o crawl
 * está vivo (e detectar travamento por ausência de eventos).
 */
export interface CrawlerStreamCallbacks {
  /** URL prestes a ser buscada (heartbeat de "estou vivo"). */
  onVisiting: (url: string) => void;
  /** Página ingerida direto (confiança alta). */
  onIngested: (url: string, domain: RagDomain) => void;
  /** Página enfileirada para revisão (confiança baixa). */
  onQueued: (url: string, domain: RagDomain) => void;
  /** Página que falhou (rede/timeout/status/ingestão) — o crawl segue. */
  onPageError: (url: string) => void;
  /** Resumo final do crawl. */
  onDone: (summary: CrawlRunResponse) => void;
  /** Erro global (crawl abortou ou stream caiu). */
  onError: (message: string) => void;
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
