import type { RuntimeSettings, RuntimeSettingsUpdate } from "@/lib/types/runtimeSettings";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

/** Erro de comunicação com o endpoint de parâmetros de execução. */
export class RuntimeSettingsApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "RuntimeSettingsApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  throw new RuntimeSettingsApiError(detail ?? mensagemPadrao, response.status);
}

/** Lê os parâmetros de execução atuais via `GET /api/admin/runtime-settings`. */
export async function getRuntimeSettings(): Promise<RuntimeSettings> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/runtime-settings`);
  } catch {
    throw new RuntimeSettingsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível carregar os parâmetros de execução.");
  }

  return (await response.json()) as RuntimeSettings;
}

/** Atualiza (parcialmente) os parâmetros de execução via `PUT /api/admin/runtime-settings`. */
export async function updateRuntimeSettings(update: RuntimeSettingsUpdate): Promise<RuntimeSettings> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/runtime-settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(update),
    });
  } catch {
    throw new RuntimeSettingsApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível aplicar os parâmetros. Tente novamente.");
  }

  return (await response.json()) as RuntimeSettings;
}
