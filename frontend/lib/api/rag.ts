import type {
  CollectionCreatePayload,
  DocumentIngestResponse,
  DocumentRegistryEntry,
  PlaygroundSearchPayload,
  PlaygroundSearchResponse,
  RagCollection,
  RagDomain,
} from "@/lib/types/rag";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

/** Erro de comunicação com os endpoints do RAG (rede ou HTTP não-2xx). */
export class RagApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "RagApiError";
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
  throw new RagApiError(message, response.status);
}

export interface UploadDocumentParams {
  file: File;
  domain: RagDomain;
  collectionId?: string;
}

/**
 * Envia um PDF/texto para ingestão no RAG via `POST /api/rag/documents`
 * (`multipart/form-data`).
 *
 * MVP: usado pela página administrativa `/admin/ingestao` — sem barra de
 * progresso nem upload em lote (um arquivo por vez), ver `docs/FRONTEND.md`.
 */
export async function uploadDocument(
  token: string,
  { file, domain, collectionId }: UploadDocumentParams,
): Promise<DocumentIngestResponse> {
  const formData = new FormData();
  formData.append("domain", domain);
  formData.append("file", file);
  if (collectionId) {
    formData.append("collection_id", collectionId);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents`, {
      method: "POST",
      body: formData,
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível enviar o documento. Tente novamente.");
  }

  return (await response.json()) as DocumentIngestResponse;
}

/**
 * Lista os documentos registrados via `GET /api/rag/documents`.
 *
 * MVP: usado pela aba "Documentos ingeridos" de `/admin/ingestao` — sem
 * paginação nem filtro no backend (lista completa, ordenada do mais recente
 * para o mais antigo).
 */
export async function listDocuments(token: string): Promise<DocumentRegistryEntry[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError(
      "Não foi possível carregar os documentos. Tente novamente.",
      response.status,
    );
  }

  return (await response.json()) as DocumentRegistryEntry[];
}

/**
 * Exclui um documento (registro + pontos no Qdrant + arquivo em disco) via
 * `DELETE /api/rag/documents/{id}`.
 */
export async function deleteDocument(token: string, id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 404
        ? "Documento não encontrado (talvez já tenha sido excluído)."
        : "Não foi possível excluir o documento. Tente novamente.";
    throw new RagApiError(message, response.status);
  }
}

/**
 * Reingere um documento já ingerido em outra collection via
 * `POST /api/rag/documents/{id}/reingest` — cria um novo documento, não
 * move o original.
 */
export async function reingestDocument(
  token: string,
  documentId: string,
  targetCollectionId: string,
): Promise<DocumentRegistryEntry> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents/${documentId}/reingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ target_collection_id: targetCollectionId }),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(
      response,
      "Não foi possível reingerir o documento. Tente novamente.",
    );
  }

  return (await response.json()) as DocumentRegistryEntry;
}

/** Lista as collections via `GET /api/rag/collections`. */
export async function listCollections(token: string): Promise<RagCollection[]> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError(
      "Não foi possível carregar as collections. Tente novamente.",
      response.status,
    );
  }

  return (await response.json()) as RagCollection[];
}

/** Cria uma collection via `POST /api/rag/collections`. */
export async function createCollection(
  token: string,
  payload: CollectionCreatePayload,
): Promise<RagCollection> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível criar a collection. Tente novamente.");
  }

  return (await response.json()) as RagCollection;
}

/** Ativa uma collection via `POST /api/rag/collections/{id}/activate`. */
export async function activateCollection(token: string, id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections/${id}/activate`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível ativar a collection. Tente novamente.");
  }
}

/** Exclui uma collection (em cascata) via `DELETE /api/rag/collections/{id}`. */
export async function deleteCollection(token: string, id: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/collections/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 409
        ? "Não é possível excluir a collection ativa. Ative outra collection antes."
        : "Não foi possível excluir a collection. Tente novamente.";
    throw new RagApiError(message, response.status);
  }
}

/** Roda a busca comparativa via `POST /api/rag/playground/search`. */
export async function runPlaygroundSearch(
  token: string,
  payload: PlaygroundSearchPayload,
): Promise<PlaygroundSearchResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/playground/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível rodar a busca. Tente novamente.");
  }

  return (await response.json()) as PlaygroundSearchResponse;
}

/**
 * Retorna a URL do endpoint de download/visualização do conteúdo de um
 * documento, com o token de admin embutido na query string (`?token=...`,
 * suportado pela mesma dependência `require_admin` do backend) — usada
 * diretamente num `<a href>`/`download`, que não permite anexar um header
 * `Authorization` customizado.
 */
export function getDocumentContentUrl(token: string, id: string): string {
  return `${API_BASE_URL}/api/rag/documents/${id}/content?token=${encodeURIComponent(token)}`;
}

/** Busca o conteúdo bruto (blob/texto) de um documento para visualização. */
export async function fetchDocumentContent(
  token: string,
  id: string,
): Promise<{ blob: Blob; contentType: string; text?: string }> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents/${id}/content`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new RagApiError("Não foi possível carregar o conteúdo do documento.", response.status);
  }

  const contentType = response.headers.get("content-type") || "";
  const blob = await response.blob();
  let text: string | undefined;

  if (
    contentType.includes("text") ||
    contentType.includes("json") ||
    contentType.includes("csv") ||
    contentType.includes("markdown")
  ) {
    text = await blob.text();
  }

  return { blob, contentType, text };
}
