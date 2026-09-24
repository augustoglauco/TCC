import type {
  ApprovedPageResponse,
  ApprovePendingPagePayload,
  CrawlerStreamCallbacks,
  CrawlRunPayload,
  CrawlRunResponse,
  PendingPage,
} from "@/lib/types/crawler";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

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
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/reject`, {
      method: "POST",
    });
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

/** Extrai `{ event, data }` de um bloco SSE (mesmo parser de `lib/api/chat.ts`). */
function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const linha of block.split("\n")) {
    if (linha.startsWith("event:")) {
      event = linha.slice("event:".length).trim();
    } else if (linha.startsWith("data:")) {
      data += linha.slice("data:".length).trim();
    }
  }
  return data ? { event, data } : null;
}

/**
 * Dispara um crawl com progresso em tempo real via `GET
 * /api/rag/crawler/run/stream` (SSE) e entrega cada evento pelos callbacks.
 * Nunca lança: erros de rede/HTTP/stream viram chamada a `onError`. Segue o
 * mesmo padrão de `sendChatMessage` (fetch + getReader), em vez de
 * `EventSource`, para poder tratar status HTTP (422/503) e reaproveitar o
 * parser de blocos SSE do projeto.
 */
export async function runCrawlerStream(
  payload: CrawlRunPayload,
  callbacks: CrawlerStreamCallbacks,
): Promise<void> {
  const params = new URLSearchParams({ url: payload.url, depth: String(payload.depth) });
  if (payload.max_pages !== undefined) {
    params.set("max_pages", String(payload.max_pages));
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/run/stream?${params.toString()}`);
  } catch {
    callbacks.onError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    return;
  }

  if (!response.ok || !response.body) {
    const detail = await extrairDetalheDeErro(response);
    callbacks.onError(
      detail ??
        (response.status === 503
          ? "Serviço de RAG temporariamente indisponível. Tente novamente."
          : "Não foi possível rodar o crawler. Tente novamente."),
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // Se o stream terminar sem `done` nem `error` (ex.: backend fecha a
  // conexão no meio), a UI ficaria sem desfecho — essa flag garante um
  // `onError` final nesse caso.
  let concluiu = false;

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex = buffer.indexOf("\n\n");
      while (sepIndex !== -1) {
        const block = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const parsed = parseSseBlock(block);
        if (parsed) {
          const json = JSON.parse(parsed.data);
          switch (parsed.event) {
            case "visitando":
              callbacks.onVisiting(json.url);
              break;
            case "ingerida":
              callbacks.onIngested(json.url, json.domain);
              break;
            case "enfileirada":
              callbacks.onQueued(json.url, json.domain);
              break;
            case "erro":
              callbacks.onPageError(json.url);
              break;
            case "done":
              concluiu = true;
              callbacks.onDone(json as CrawlRunResponse);
              break;
            case "error":
              concluiu = true;
              callbacks.onError(json.detail ?? "Erro inesperado. Tente novamente.");
              break;
          }
        }
        sepIndex = buffer.indexOf("\n\n");
      }
    }
  } catch {
    callbacks.onError("Conexão perdida durante o crawl. Tente novamente.");
    return;
  }

  if (!concluiu) {
    callbacks.onError("Resposta incompleta do servidor (crawl pode ter sido interrompido).");
  }
}
