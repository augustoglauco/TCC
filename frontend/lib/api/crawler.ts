import type {
  ApprovedPageResponse,
  ApprovePendingPagePayload,
  CrawlerStreamCallbacks,
  CrawlRunPayload,
  CrawlRunResponse,
  PendingPage,
} from "@/lib/types/crawler";
import type { RagDomain } from "@/lib/types/rag";
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

async function _mensagemDeErro(response: Response, mensagemPadrao: string): Promise<string> {
  const detail = await extrairDetalheDeErro(response);
  return (
    detail ??
    (response.status === 503
      ? "Serviço de RAG temporariamente indisponível. Tente novamente."
      : mensagemPadrao)
  );
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  throw new CrawlerApiError(await _mensagemDeErro(response, mensagemPadrao), response.status);
}

/** Lista a fila de revisão via `GET /api/rag/crawler/pending`. */
export async function listPendingPages(token: string): Promise<PendingPage[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending`, {
      headers: { Authorization: `Bearer ${token}` },
    });
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
  token: string,
  id: string,
  payload: ApprovePendingPagePayload,
): Promise<ApprovedPageResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
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
export async function rejectPendingPage(token: string, id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/pending/${id}/reject`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
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

/** Entrega um evento SSE ao callback certo. Retorna true se o evento encerra o stream. */
function despacharEvento(
  event: string,
  json: { url: string; domain?: RagDomain; detail?: string },
  callbacks: CrawlerStreamCallbacks,
): boolean {
  switch (event) {
    case "visitando":
      callbacks.onVisiting(json.url);
      return false;
    case "enfileirada":
      callbacks.onQueued(json.url, json.domain as RagDomain);
      return false;
    case "erro":
      callbacks.onPageError(json.url);
      return false;
    case "done":
      callbacks.onDone(json as unknown as CrawlRunResponse);
      return true;
    case "error":
      callbacks.onError(json.detail ?? "Erro inesperado. Tente novamente.");
      return true;
    default:
      return false;
  }
}

/** Consome os blocos SSE completos do buffer; devolve o resto e se algum evento encerrou o stream. */
function consumirBlocos(
  buffer: string,
  callbacks: CrawlerStreamCallbacks,
): { resto: string; concluiu: boolean } {
  let resto = buffer;
  let concluiu = false;
  let sepIndex = resto.indexOf("\n\n");
  while (sepIndex !== -1) {
    const parsed = parseSseBlock(resto.slice(0, sepIndex));
    resto = resto.slice(sepIndex + 2);
    if (parsed && despacharEvento(parsed.event, JSON.parse(parsed.data), callbacks)) {
      concluiu = true;
    }
    sepIndex = resto.indexOf("\n\n");
  }
  return { resto, concluiu };
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
  token: string,
  payload: CrawlRunPayload,
  callbacks: CrawlerStreamCallbacks,
): Promise<void> {
  const params = _montarParams(payload);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/crawler/run/stream?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    callbacks.onError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    return;
  }

  if (!response.ok || !response.body) {
    callbacks.onError(
      await _mensagemDeErro(response, "Não foi possível rodar o crawler. Tente novamente."),
    );
    return;
  }

  await _lerStream(response.body, callbacks);
}

function _montarParams(payload: CrawlRunPayload): URLSearchParams {
  const params = new URLSearchParams({ url: payload.url, depth: String(payload.depth) });
  if (payload.max_pages !== undefined) {
    params.set("max_pages", String(payload.max_pages));
  }
  if (payload.collection_id) {
    params.set("collection_id", payload.collection_id);
  }
  return params;
}

/** Lê o corpo SSE até o fim, entregando eventos; garante um desfecho (`onError`) se não vier `done`/`error`. */
async function _lerStream(
  body: ReadableStream<Uint8Array>,
  callbacks: CrawlerStreamCallbacks,
): Promise<void> {
  const reader = body.getReader();
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

      const consumo = consumirBlocos(buffer, callbacks);
      buffer = consumo.resto;
      concluiu ||= consumo.concluiu;
    }
  } catch {
    callbacks.onError("Conexão perdida durante o crawl. Tente novamente.");
    return;
  }

  if (!concluiu) {
    callbacks.onError("Resposta incompleta do servidor (crawl pode ter sido interrompido).");
  }
}
