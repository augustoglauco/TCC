import { afterEach, describe, expect, it, vi } from "vitest";

import { RagApiError, activateCollection, createCollection } from "@/lib/api/rag";
import type { CollectionCreatePayload } from "@/lib/types/rag";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("activateCollection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("preserva a mensagem de erro específica retornada pelo backend (paridade com activateModel)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse({ detail: "Collection não encontrada." }, 404)),
    );

    await expect(activateCollection("col-1")).rejects.toMatchObject({
      message: "Collection não encontrada.",
      status: 404,
    });
  });

  it("usa a mensagem genérica de fallback quando o backend não retorna detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    await expect(activateCollection("col-1")).rejects.toBeInstanceOf(RagApiError);
    await expect(activateCollection("col-1")).rejects.toMatchObject({
      message: "Não foi possível ativar a collection. Tente novamente.",
    });
  });
});

describe("createCollection", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("extrai a mensagem de um erro 422 de validação do Pydantic (detail como array)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              {
                loc: ["body", "chunk_overlap"],
                msg: "chunk_overlap deve ser menor que chunk_size",
                type: "value_error",
              },
            ],
          },
          422,
        ),
      ),
    );

    const payload: CollectionCreatePayload = {
      name: "col-teste",
      embedding_model: "text-embedding-3-small",
      distance_metric: "cosine",
      chunk_size: 100,
      chunk_overlap: 200,
      hnsw: {
        m: 16,
        ef_construct: 100,
        full_scan_threshold: 10000,
        max_indexing_threads: 0,
        on_disk: false,
        payload_m: null,
      },
      quantization: { type: "none" },
      payload_indexes: [],
    };

    await expect(createCollection(payload)).rejects.toMatchObject({
      message: "chunk_overlap deve ser menor que chunk_size",
      status: 422,
    });
  });
});
