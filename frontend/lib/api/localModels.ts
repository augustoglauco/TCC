import type { LocalModelsListResponse, PullStatusResponse } from "@/lib/types/localModels";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

/** Erro de comunicação com os endpoints do gerenciador de modelos locais. */
export class LocalModelsApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "LocalModelsApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  throw new LocalModelsApiError(detail ?? mensagemPadrao, response.status);
}

/** Lista os modelos locais via `GET /api/admin/local-models`. */
export async function listLocalModels(): Promise<LocalModelsListResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models`);
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new LocalModelsApiError("Não foi possível carregar os modelos locais. Tente novamente.", response.status);
  }

  return (await response.json()) as LocalModelsListResponse;
}

/** Ativa um modelo já baixado via `POST /api/admin/local-models/activate`. */
export async function activateModel(name: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models/activate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível ativar o modelo. Tente novamente.");
  }
}

/** Dispara o download de um modelo via `POST /api/admin/local-models/pull` (não bloqueia — retorna assim que a tarefa é iniciada). */
export async function pullModel(name: string): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/local-models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível iniciar o download. Tente novamente.");
  }
}

/**
 * Consulta o progresso de um download via
 * `GET /api/admin/local-models/pull-status?name=...` — usado em polling
 * pelo componente de formulário de download.
 */
export async function getPullStatus(name: string): Promise<PullStatusResponse> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/admin/local-models/pull-status?name=${encodeURIComponent(name)}`,
    );
  } catch {
    throw new LocalModelsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    throw new LocalModelsApiError("Não foi possível consultar o progresso do download.", response.status);
  }

  return (await response.json()) as PullStatusResponse;
}
