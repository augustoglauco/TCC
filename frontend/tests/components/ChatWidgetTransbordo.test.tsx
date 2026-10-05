import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import MessageBubble from "@/components/chat/MessageBubble";
import { solicitarTransbordo, claimConversa, enviarMensagemAtendente } from "@/lib/api/adminAtendimento";
import type { ChatUIMessage } from "@/lib/types/chat";

describe("Atendimento Humano - Chat Widget & MessageBubble", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("renderiza balão de mensagem de atendente humano com estilo esmeralda e badge", () => {
    const message: ChatUIMessage = {
      id: "msg-atendente-1",
      role: "atendente",
      text: "Olá! Sou o atendente Carlos e vou te ajudar com seu pedido.",
      atendenteNome: "Carlos Silva",
    };

    render(<MessageBubble message={message} />);

    // Verifica texto da mensagem
    expect(
      screen.getByText("Olá! Sou o atendente Carlos e vou te ajudar com seu pedido."),
    ).toBeInTheDocument();

    // Verifica badge do atendente humano
    const badge = screen.getByTestId("message-atendente-badge");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveTextContent("Carlos Silva");
    expect(badge).toHaveTextContent("Atendente Humano");

    // Verifica que o balão tem estilização esmeralda
    const bubble = screen.getByTestId("message-bubble");
    expect(bubble.className).toContain("bg-emerald-50");
    expect(bubble.className).toContain("border-emerald-300");
  });

  it("chama solicitarTransbordo com a rota e payload corretos", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "aguardando_humano", conversation_id: "conv-123" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const res = await solicitarTransbordo("conv-123", "solicitacao_manual");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/chat/conversations/conv-123/transbordo"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ motivo: "solicitacao_manual" }),
      }),
    );
    expect(res.status).toBe("aguardando_humano");
  });

  it("chama claimConversa e enviarMensagemAtendente no adminAtendimento", async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.includes("/claim")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: "em_atendimento_humano" }),
        });
      }
      if (url.includes("/mensagem")) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ id: 10, papel: "atendente", texto: "Resposta enviada" }),
        });
      }
      return Promise.reject(new Error("URL não mapeada"));
    });
    vi.stubGlobal("fetch", fetchMock);

    const claimRes = await claimConversa("conv-99", "op-1", "Operador 1", "token-admin");
    expect(claimRes.status).toBe("em_atendimento_humano");

    const msgRes = await enviarMensagemAtendente(
      "conv-99",
      "Operador 1",
      "Resposta enviada",
      "token-admin",
    );
    expect(msgRes.papel).toBe("atendente");
  });
});
