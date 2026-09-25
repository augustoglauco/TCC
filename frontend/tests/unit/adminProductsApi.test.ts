import { describe, it, expect, vi } from "vitest";
import {
  fetchAdminProducts,
  createAdminProduct,
  updateAdminProduct,
  deleteAdminProduct,
  confirmCatalogExtraction,
} from "@/lib/api/adminProducts";

describe("adminProducts API client", () => {
  it("monta query string com filtros e retorna lista de produtos", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [{ id: 1, nome: "Câmera" }], total: 1 }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await fetchAdminProducts({ termo: "Câmera", categoria: "CFTV" });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos?termo=C%C3%A2mera&categoria=CFTV"),
      expect.any(Object)
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

    const result = await createAdminProduct({ nome: "Gravador NVD", preco: 500 });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos"),
      expect.objectContaining({ method: "POST" })
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

    const result = await confirmCatalogExtraction({
      produtos: [{ nome: "Prod 1", preco: 100 }],
    });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/admin/produtos/catalogo/confirmar"),
      expect.objectContaining({ method: "POST" })
    );
    expect(result.criados).toBe(1);
    vi.unstubAllGlobals();
  });
});
