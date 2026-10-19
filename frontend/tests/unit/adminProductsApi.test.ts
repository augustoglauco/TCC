import { describe, it, expect, vi } from "vitest";
import {
  fetchAdminProducts,
  createAdminProduct,
  confirmCatalogExtraction,
  deleteAdminProductImage,
  extractCatalogStream,
} from "@/lib/api/adminProducts";

describe("adminProducts API client", () => {
  it("monta query string com filtros e retorna lista de produtos", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 1, nome: "Câmera" }], total: 1 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await fetchAdminProducts("mock-token", { termo: "Câmera", categoria: "CFTV" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos?termo=C%C3%A2mera&categoria=CFTV"),
      expect.any(Object),
    );
    expect(result.items).toHaveLength(1);
    vi.unstubAllGlobals();
  });

  it("cria produto via POST", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 10, nome: "Gravador NVD", preco: 500 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await createAdminProduct("mock-token", { nome: "Gravador NVD", preco: 500 });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.id).toBe(10);
    vi.unstubAllGlobals();
  });

  it("confirma extracao de catalogo", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ criados: 1, produtos: [{ id: 1, nome: "Prod 1" }] }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await confirmCatalogExtraction("mock-token", {
      produtos: [{ nome: "Prod 1", preco: 100 }],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos/catalogo/confirmar"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.criados).toBe(1);
    vi.unstubAllGlobals();
  });

  it("busca categorias distintas do backend", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ["CFTV", "Alarmes", "Redes"],
    });
    vi.stubGlobal("fetch", mockFetch);

    const { fetchAdminCategories } = await import("@/lib/api/adminProducts");
    const result = await fetchAdminCategories("mock-token");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos/categorias"),
      expect.any(Object),
    );
    expect(result).toEqual(["CFTV", "Alarmes", "Redes"]);
    vi.unstubAllGlobals();
  });

  it("envia imagem temporaria via uploadTempImage", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ imagem_temp_url: "/api/uploads/produtos/temp/crop_123.jpg" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const { uploadTempImage } = await import("@/lib/api/adminProducts");
    const file = new File(["dummy"], "teste.jpg", { type: "image/jpeg" });
    const url = await uploadTempImage("mock-token", file);
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos/upload-temp"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(url).toBe("/api/uploads/produtos/temp/crop_123.jpg");
    vi.unstubAllGlobals();
  });

  it("exclui imagem com sucesso via DELETE", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(deleteAdminProductImage("mock-token", 1, 10)).resolves.toBeUndefined();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos/1/imagens/10"),
      expect.objectContaining({ method: "DELETE" }),
    );
    vi.unstubAllGlobals();
  });

  it("tolera status 404 de forma idempotente ao excluir imagem já inexistente", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(deleteAdminProductImage("mock-token", 1, 10)).resolves.toBeUndefined();
    vi.unstubAllGlobals();
  });

  it("lança erro em falhas reais de servidor (ex: 500) ao excluir imagem", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(deleteAdminProductImage("mock-token", 1, 10)).rejects.toThrow(
      "Erro ao excluir imagem (500)",
    );
    vi.unstubAllGlobals();
  });

  it("anexa page_range no FormData em extractCatalogStream quando fornecido", async () => {
    let capturedBody = null as FormData | null;
    const mockFetch = vi.fn().mockImplementation(async (_url, options) => {
      capturedBody = options?.body as FormData;
      return {
        ok: true,
        body: {
          getReader: () => ({
            read: vi.fn().mockResolvedValue({ done: true, value: undefined }),
          }),
        },
      };
    });
    vi.stubGlobal("fetch", mockFetch);

    const file = new File(["dummy pdf"], "catalogo.pdf", { type: "application/pdf" });
    await extractCatalogStream("mock-token", [file], { pageRange: "1-5, 8" }, {});

    expect(capturedBody).not.toBeNull();
    expect(capturedBody?.get("page_range")).toBe("1-5, 8");
    vi.unstubAllGlobals();
  });

  it("despacha eventos SSE de extractCatalogStream para os callbacks e ignora blocos inválidos", async () => {
    const enc = new TextEncoder();
    const chunks = [
      'event: progresso\ndata: {"a":1}\n\nevent: pagina_concluida\ndata: {"p":2}\n\n',
      'event: done\ndata: {"total_produtos":3,"total_paginas":4}\n\nevent: done\ndata: {x\n\n',
    ];
    let n = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        body: {
          getReader: () => ({
            read: async () =>
              n < chunks.length
                ? { done: false, value: enc.encode(chunks[n++]) }
                : { done: true, value: undefined },
          }),
        },
      }),
    );
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const cb = { onProgress: vi.fn(), onPageComplete: vi.fn(), onDone: vi.fn(), onError: vi.fn() };

    await extractCatalogStream("t", [], {}, cb);

    expect(cb.onProgress).toHaveBeenCalledWith({ a: 1 });
    expect(cb.onPageComplete).toHaveBeenCalledWith({ p: 2 });
    expect(cb.onDone).toHaveBeenCalledWith({ total_produtos: 3, total_paginas: 4 });
    expect(warn).toHaveBeenCalledTimes(1);
    expect(cb.onError).not.toHaveBeenCalled();
    warn.mockRestore();
    vi.unstubAllGlobals();
  });

  it("chama onError em extractCatalogStream quando a resposta falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, body: null }));
    const onError = vi.fn();
    await extractCatalogStream("t", [], {}, { onError });
    expect(onError).toHaveBeenCalledWith("Erro ao iniciar extração (500)");
    vi.unstubAllGlobals();
  });
});
