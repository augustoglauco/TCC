import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";

vi.mock("@/lib/api/modelCatalog", () => ({
  getModelCharacteristics: vi.fn(),
  refreshModelCharacteristics: vi.fn(),
  ModelCatalogApiError: class extends Error {},
}));

import { getModelCharacteristics, refreshModelCharacteristics } from "@/lib/api/modelCatalog";

const mockGet = vi.mocked(getModelCharacteristics);
const mockRefresh = vi.mocked(refreshModelCharacteristics);

const CARACTERISTICAS = {
  source: "openrouter" as const,
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

describe("useModelCharacteristics", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("busca no mount e expõe o resultado", async () => {
    mockGet.mockResolvedValue(CARACTERISTICAS);

    const { result } = renderHook(() =>
      useModelCharacteristics("openrouter", "openai/gpt-4o-mini"),
    );

    expect(result.current.loading).toBe(true);

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toEqual(CARACTERISTICAS);
    expect(mockGet).toHaveBeenCalledWith("openrouter", "openai/gpt-4o-mini");
  });

  it("não refaz a busca para a mesma tag já cacheada", async () => {
    // Tag exclusiva deste teste: o cache do hook é module-level e
    // sobrevive entre `it()` do mesmo arquivo (vitest isola módulos por
    // arquivo, não por teste), então reusar a tag de outro teste faria
    // este `renderHook` nascer com o cache já quente.
    mockGet.mockResolvedValue(CARACTERISTICAS);

    const { unmount } = renderHook(() =>
      useModelCharacteristics("openrouter", "openai/gpt-4o-mini-cache-proprio"),
    );
    await waitFor(() => expect(mockGet).toHaveBeenCalledTimes(1));
    unmount();

    renderHook(() => useModelCharacteristics("openrouter", "openai/gpt-4o-mini-cache-proprio"));

    expect(mockGet).toHaveBeenCalledTimes(1);
  });

  it("duas montagens simultâneas da mesma tag compartilham uma única requisição em voo", async () => {
    // Achado #1 da revisão final: `openai/gpt-4o-mini` aparece em dois cards
    // ao mesmo tempo (POPULAR_MODELS e histórico) — ambos montam o hook para
    // a mesma tag no mesmo ciclo de render, antes de qualquer fetch
    // resolver. Sem deduplicação, cada um dispara seu próprio GET, e no
    // backend os dois `get_or_fetch` tentam inserir a mesma linha.
    let resolverFetch: (valor: typeof CARACTERISTICAS) => void = () => {};
    const fetchPendente = new Promise<typeof CARACTERISTICAS>((resolve) => {
      resolverFetch = resolve;
    });
    mockGet.mockReturnValue(fetchPendente);

    const { result: resultA } = renderHook(() =>
      useModelCharacteristics("openrouter", "tag-compartilhada-simultanea"),
    );
    const { result: resultB } = renderHook(() =>
      useModelCharacteristics("openrouter", "tag-compartilhada-simultanea"),
    );

    expect(resultA.current.loading).toBe(true);
    expect(resultB.current.loading).toBe(true);
    expect(mockGet).toHaveBeenCalledTimes(1);

    resolverFetch(CARACTERISTICAS);
    await waitFor(() => expect(resultA.current.loading).toBe(false));
    await waitFor(() => expect(resultB.current.loading).toBe(false));

    expect(mockGet).toHaveBeenCalledTimes(1);
    expect(resultA.current.data).toEqual(CARACTERISTICAS);
    expect(resultB.current.data).toEqual(CARACTERISTICAS);
  });

  it("refresh() chama o endpoint de refresh e atualiza o estado", async () => {
    mockGet.mockResolvedValue(null);
    mockRefresh.mockResolvedValue(CARACTERISTICAS);

    const { result } = renderHook(() =>
      useModelCharacteristics("openrouter", "modelo-ainda-nao-cacheado"),
    );
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockRefresh).toHaveBeenCalledWith("openrouter", "modelo-ainda-nao-cacheado");
    expect(result.current.data).toEqual(CARACTERISTICAS);
  });
});
