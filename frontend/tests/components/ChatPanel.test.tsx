import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatPanel from "@/components/chat/ChatPanel";
import { ChatApiError } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";

vi.mock("@/lib/api/chat", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/chat")>("@/lib/api/chat");
  return {
    ...actual,
    sendChatMessage: vi.fn(),
  };
});

import { sendChatMessage } from "@/lib/api/chat";

const mockedSendChatMessage = vi.mocked(sendChatMessage);

function resetStore() {
  useChatStore.setState({ isOpen: true, conversationId: "", messages: [] });
}

describe("ChatPanel", () => {
  beforeEach(() => {
    resetStore();
    mockedSendChatMessage.mockReset();
  });

  it("envia mensagem de texto e exibe a resposta do assistente", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      conversation_id: "conv-1",
      message: "Temos esse produto em estoque.",
      domain: "vendas",
      backend_used: "local",
      escalation_reason: "nenhum",
    });

    render(<ChatPanel />);

    await user.type(screen.getByLabelText("Mensagem"), "Vocês têm o produto X?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Vocês têm o produto X?")).toBeInTheDocument();
    expect(await screen.findByText("Temos esse produto em estoque.")).toBeInTheDocument();
    expect(screen.getByTestId("message-domain-label")).toHaveTextContent("Vendas");
    expect(mockedSendChatMessage).toHaveBeenCalledWith("Vocês têm o produto X?", undefined);
  });

  it("mostra bolha de erro com opção de tentar novamente e permite reenviar", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockRejectedValueOnce(
      new ChatApiError("Serviço temporariamente indisponível. Tente novamente.", 503),
    );
    mockedSendChatMessage.mockResolvedValueOnce({
      conversation_id: "conv-1",
      message: "Tudo certo agora.",
      domain: "suporte",
      backend_used: "local",
      escalation_reason: "nenhum",
    });

    render(<ChatPanel />);

    await user.type(screen.getByLabelText("Mensagem"), "Preciso de ajuda");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Serviço temporariamente indisponível. Tente novamente.");

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
    expect(await screen.findByText("Tudo certo agora.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
  });
});
