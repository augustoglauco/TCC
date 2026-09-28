import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchProductById } from "@/lib/api/products";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("fetchProductById", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("retorna os dados do produto quando a resposta é 200 OK", async () => {
    const mockProduct = {
      id: 1,
      nome: "Gravador NVR 16 Canais",
      descricao: "Gravador de vídeo IP",
      preco: 1200,
      categoria: "CFTV",
      estoques: [],
      imagens: [],
    };

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(mockProduct, 200)));

    const result = await fetchProductById(1);
    expect(result).toEqual(mockProduct);
  });

  it("lança erro amigável quando produto não é encontrado (404)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Not found" }, 404)));

    await expect(fetchProductById(999)).rejects.toThrow("Produto não encontrado.");
  });

  it("lança erro genérico em caso de falha de servidor (500)", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response("Internal Server Error", {
            status: 500,
            statusText: "Internal Server Error",
          }),
        ),
    );

    await expect(fetchProductById(1)).rejects.toThrow(/Erro ao buscar produto/);
  });
});
