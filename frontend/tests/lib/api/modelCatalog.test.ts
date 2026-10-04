import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ModelCatalogApiError,
  getModelCharacteristics,
  refreshModelCharacteristics,
} from "@/lib/api/modelCatalog";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

const CARACTERISTICAS_EXEMPLO = {
  source: "openrouter",
  tag: "openai/gpt-4o-mini",
  is_multimodal: true,
  input_modalities: ["text", "image"],
  output_modalities: ["text"],
  context_length: 128000,
  parameter_size: null,
  quantization: null,
  pricing_prompt_per_1k: 0.00015,
  pricing_completion_per_1k: 0.0006,
  knowledge_cutoff: "2023-10-31",
  fetched_at: "2026-10-03T12:00:00Z",
};

describe("getModelCharacteristics", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("devolve as características quando a resposta é 200", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(CARACTERISTICAS_EXEMPLO, 200)));

    const resultado = await getModelCharacteristics("openrouter", "openai/gpt-4o-mini");

    expect(resultado).toEqual(CARACTERISTICAS_EXEMPLO);
  });

  it("devolve null quando a resposta é 404 (sem característica pra essa tag)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "não achado" }, 404)));

    const resultado = await getModelCharacteristics("openrouter", "tag/inexistente");

    expect(resultado).toBeNull();
  });

  it("lança ModelCatalogApiError em erro 500", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    await expect(getModelCharacteristics("openrouter", "x")).rejects.toBeInstanceOf(
      ModelCatalogApiError,
    );
  });
});

describe("refreshModelCharacteristics", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("faz POST para o endpoint de refresh e devolve as características atualizadas", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(CARACTERISTICAS_EXEMPLO, 200));
    vi.stubGlobal("fetch", mockFetch);

    const resultado = await refreshModelCharacteristics("openrouter", "openai/gpt-4o-mini");

    expect(resultado).toEqual(CARACTERISTICAS_EXEMPLO);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/characteristics/refresh"),
      expect.objectContaining({ method: "POST" }),
    );
  });
});
