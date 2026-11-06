import { afterEach, describe, expect, it, vi } from "vitest";

import { urlComprovantePedido } from "@/lib/api/adminPedidos";

describe("urlComprovantePedido", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("aponta para a rota do backend com o token na query", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://backend:8000/");
    expect(urlComprovantePedido("abc-123", "mock-token-1")).toBe(
      "http://backend:8000/api/admin/pedidos/abc-123/comprovante?token=mock-token-1",
    );
  });

  it("codifica o token e omite a query sem token", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "http://backend:8000");
    expect(urlComprovantePedido("abc-123", "a b&c")).toContain("?token=a%20b%26c");
    expect(urlComprovantePedido("abc-123", null)).toBe(
      "http://backend:8000/api/admin/pedidos/abc-123/comprovante",
    );
  });
});
