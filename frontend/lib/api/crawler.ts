import type {
  ApprovedPageResponse,
  ApprovePendingPagePayload,
  CrawlRunPayload,
  CrawlRunResponse,
  PendingPage,
} from "@/lib/types/crawler";
import { extrairDetalheDeErro } from "@/lib/api/errors";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com os endpoints do crawler (rede ou HTTP não-2xx). */
export class CrawlerApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "CrawlerApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  const message =
    detail ??
    (response.status === 503
      ? "Serviço de RAG temporariamente indisponível. Tente novamente."
      : mensagemPadrao);
  throw new CrawlerApiError(message, response.status);
}

/** Dispara um crawl a partir de uma URL semente via `POST /api/rag/crawler/run`. */
export async function runCrawler(payload: CrawlRunPayload): Promise<CrawlRunResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível rodar o crawler. Tente novamente.");
  }

  return (await response.json()) as CrawlRunResponse;
}

/** Lista a fila de revisão via `GET /api/rag/crawler/pending`. */
export async function listPendingPages(): Promise<PendingPage[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending`);
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new CrawlerApiError(
      "Não foi possível carregar a fila de revisão. Tente novamente.",
      response.status,
    );
  }

  return (await response.json()) as PendingPage[];
}

/** Aprova uma página pendente via `POST /api/rag/crawler/pending/{id}/approve`. */
export async function approvePendingPage(
  id: string,
  payload: ApprovePendingPagePayload,
): Promise<ApprovedPageResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível aprovar a página. Tente novamente.");
  }

  return (await response.json()) as ApprovedPageResponse;
}

/** Rejeita uma página pendente via `POST /api/rag/crawler/pending/{id}/reject`. */
export async function rejectPendingPage(id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/reject`, { method: "POST" });
  } catch {
    throw new CrawlerApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 404
        ? "Página pendente não encontrada (talvez já tenha sido revisada)."
        : "Não foi possível rejeitar a página. Tente novamente.";
    throw new CrawlerApiError(message, response.status);
  }
}
