import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchCurrentUser, login } from "@/lib/api/auth";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("auth API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("login", () => {
    it("retorna token e dados do usuário quando login for bem-sucedido", async () => {
      const mockResult = {
        token: "mock-token-123",
        user: {
          id: 1,
          email: "ana.recorrente@example.com",
          nome: "Ana Recorrente",
          perfil: "Cliente",
          perfil_motivo: "3 compras recentes",
        },
      };

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(mockResult, 200)));

      const res = await login("ana.recorrente@example.com", "12345");
      expect(res).toEqual(mockResult);
    });

    it("lança erro amigável quando credenciais forem inválidas", async () => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            jsonResponse({ detail: "Senha incorreta para teste mock. Utilize '12345'." }, 401),
          ),
      );

      await expect(login("ana.recorrente@example.com", "senha_errada")).rejects.toThrow(
        "Senha incorreta para teste mock. Utilize '12345'.",
      );
    });
  });

  describe("fetchCurrentUser", () => {
    it("retorna os dados do usuário autenticado", async () => {
      const mockUser = {
        id: 2,
        email: "bruno.unico@example.com",
        nome: "Bruno Único",
        perfil: "Esporádico",
        perfil_motivo: "1 compra recente",
      };

      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(mockUser, 200)));

      const res = await fetchCurrentUser("bruno.unico@example.com");
      expect(res).toEqual(mockUser);
    });

    it("lança erro quando usuário não for encontrado", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Not found" }, 404)));

      await expect(fetchCurrentUser("nao.existe@example.com")).rejects.toThrow(
        "Usuário não encontrado.",
      );
    });
  });
});
