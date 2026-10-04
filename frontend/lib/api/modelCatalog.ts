import type { ModelCharacteristics, ModelSource } from "@/lib/types/modelCatalog";
import { extrairDetalheDeErro } from "@/lib/api/errors";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

/** Erro de comunicação com os endpoints de características de modelo. */
export class ModelCatalogApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ModelCatalogApiError";
    this.status = status;
  }
}

async function _lancarErroComDetalhe(response: Response, mensagemPadrao: string): Promise<never> {
  const detail = await extrairDetalheDeErro(response);
  throw new ModelCatalogApiError(detail ?? mensagemPadrao, response.status);
}

/**
 * Busca as características cacheadas (ou recém-buscadas) de um modelo via
 * `GET /api/admin/model-catalog/characteristics`. `null` quando a fonte não
 * tem característica pra essa tag (404) — não é um erro.
 */
export async function getModelCharacteristics(
  source: ModelSource,
  tag: string,
): Promise<ModelCharacteristics | null> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/admin/model-catalog/characteristics?source=${encodeURIComponent(
        source,
      )}&tag=${encodeURIComponent(tag)}`,
    );
  } catch {
    throw new ModelCatalogApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (response.status === 404) return null;
  if (!response.ok) {
    await _lancarErroComDetalhe(response, "Não foi possível obter as características do modelo.");
  }

  return (await response.json()) as ModelCharacteristics;
}

/** Força nova busca na fonte via `POST .../characteristics/refresh`, ignorando o cache. */
export async function refreshModelCharacteristics(
  source: ModelSource,
  tag: string,
): Promise<ModelCharacteristics | null> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/admin/model-catalog/characteristics/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, tag }),
    });
  } catch {
    throw new ModelCatalogApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (response.status === 404) return null;
  if (!response.ok) {
    await _lancarErroComDetalhe(
      response,
      "Não foi possível atualizar as características do modelo.",
    );
  }

  return (await response.json()) as ModelCharacteristics;
}
