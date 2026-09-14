import type { DocumentIngestResponse, RagDomain } from "@/lib/types/rag";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com `POST /api/rag/documents` (rede ou HTTP não-2xx). */
export class RagApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "RagApiError";
    this.status = status;
  }
}

export interface UploadDocumentParams {
  file: File;
  domain: RagDomain;
}

/**
 * Envia um PDF/texto para ingestão no RAG via `POST /api/rag/documents`
 * (`multipart/form-data`).
 *
 * MVP: usado pela página administrativa `/admin/ingestao` — sem barra de
 * progresso nem upload em lote (um arquivo por vez), ver `docs/FRONTEND.md`.
 */
export async function uploadDocument({
  file,
  domain,
}: UploadDocumentParams): Promise<DocumentIngestResponse> {
  const formData = new FormData();
  formData.append("domain", domain);
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/rag/documents`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new RagApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    // O backend já calcula uma mensagem específica em `detail` (formato não
    // suportado, PDF corrompido, etc. — ver `backend/src/app/api/rag.py`);
    // só cai numa mensagem genérica se a resposta não vier no formato
    // esperado (ex.: erro 502 de um proxy, sem JSON).
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    const message =
      detail ??
      (response.status === 503
        ? "Serviço de RAG temporariamente indisponível. Tente novamente."
        : "Não foi possível enviar o documento. Tente novamente.");
    throw new RagApiError(message, response.status);
  }

  return (await response.json()) as DocumentIngestResponse;
}
