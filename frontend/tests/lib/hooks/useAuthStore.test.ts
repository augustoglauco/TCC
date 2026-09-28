import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("useAuthStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
    useChatStore.setState({
      conversationId: "conv-anterior",
      messages: [{ id: "m1", role: "user", text: "mensagem antiga" }],
    });
  });

  it("ao fazer login, armazena usuário e limpa o chat", async () => {
    const mockResult = {
      token: "mock-token-xyz",
      user: {
        id: 1,
        email: "ana.recorrente@example.com",
        nome: "Ana",
        perfil: "Cliente",
      },
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(mockResult, 200)));

    await useAuthStore.getState().login("ana.recorrente@example.com", "12345");

    expect(useAuthStore.getState().user?.email).toBe("ana.recorrente@example.com");
    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().conversationId).not.toBe("conv-anterior");
  });

  it("ao fazer logout, remove usuário e limpa o chat para não herdar dados", () => {
    useAuthStore.setState({
      user: {
        id: 1,
        email: "ana.recorrente@example.com",
        nome: "Ana",
        perfil: "Cliente",
      },
      token: "mock-token",
    });
    useChatStore.setState({
      conversationId: "conv-ana",
      messages: [{ id: "m2", role: "assistant", text: "Olá Ana" }],
    });

    useAuthStore.getState().logout();

    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().token).toBeNull();
    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().conversationId).not.toBe("conv-ana");
  });
});
