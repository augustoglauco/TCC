import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatWidget from "@/components/chat/ChatWidget";
import { fetchConversationHistory } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";

vi.mock("@/lib/api/chat", () => ({
  fetchConversationHistory: vi.fn(),
  sendChatMessage: vi.fn(),
}));

const mockedFetchHistory = vi.mocked(fetchConversationHistory);

const HISTORICO = [
  { id: "m1", role: "user" as const, text: "Quanto custa o GD-15?" },
  { id: "m2", role: "assistant" as const, text: "R$ 24.900,00", domain: "vendas" as const },
];

beforeEach(() => {
  mockedFetchHistory.mockReset();
  useChatStore.setState({ isOpen: false, conversationId: "conv-1", messages: [] });
});

describe("ChatWidget — retomada da conversa (R9)", () => {
  it("carrega o histórico gravado ao montar", async () => {
    mockedFetchHistory.mockResolvedValue(HISTORICO);

    render(<ChatWidget />);

    await waitFor(() => expect(useChatStore.getState().messages).toEqual(HISTORICO));
    expect(mockedFetchHistory).toHaveBeenCalledWith("conv-1");
  });

  it("não sobrescreve mensagens que já estão na tela", async () => {
    const naTela = [{ id: "n1", role: "user" as const, text: "mensagem nova" }];
    useChatStore.setState({ messages: naTela });
    mockedFetchHistory.mockResolvedValue(HISTORICO);

    render(<ChatWidget />);

    await waitFor(() => expect(mockedFetchHistory).toHaveBeenCalled());
    expect(useChatStore.getState().messages).toEqual(naTela);
  });

  it("falha ao buscar o histórico deixa o chat vazio", async () => {
    mockedFetchHistory.mockResolvedValue(null);

    render(<ChatWidget />);

    await waitFor(() => expect(mockedFetchHistory).toHaveBeenCalled());
    expect(useChatStore.getState().messages).toEqual([]);
  });
});
