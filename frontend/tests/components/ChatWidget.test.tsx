import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatWidget from "@/components/chat/ChatWidget";
import { fetchConversationSnapshot } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";

vi.mock("@/lib/api/chat", () => ({
  fetchConversationSnapshot: vi.fn(),
  sendChatMessage: vi.fn(),
}));

const mockedFetchSnapshot = vi.mocked(fetchConversationSnapshot);

const HISTORICO = [
  { id: "m1", role: "user" as const, text: "Quanto custa o GD-15?" },
  { id: "m2", role: "assistant" as const, text: "R$ 24.900,00", domain: "vendas" as const },
];

beforeEach(() => {
  mockedFetchSnapshot.mockReset();
  useChatStore.setState({
    isOpen: false,
    conversationId: "conv-1",
    messages: [],
    humanAttendanceStatus: null,
  });
});

describe("ChatWidget — retomada da conversa (R9)", () => {
  it("carrega o histórico gravado ao montar", async () => {
    mockedFetchSnapshot.mockResolvedValue({ status: "aberta", messages: HISTORICO });

    render(<ChatWidget />);

    await waitFor(() => expect(useChatStore.getState().messages).toEqual(HISTORICO));
    expect(mockedFetchSnapshot).toHaveBeenCalledWith("conv-1");
  });

  it("não sobrescreve mensagens que já estão na tela", async () => {
    const naTela = [{ id: "n1", role: "user" as const, text: "mensagem nova" }];
    useChatStore.setState({ messages: naTela });
    mockedFetchSnapshot.mockResolvedValue({ status: "aberta", messages: HISTORICO });

    render(<ChatWidget />);

    await waitFor(() => expect(mockedFetchSnapshot).toHaveBeenCalled());
    expect(useChatStore.getState().messages).toEqual(naTela);
  });

  it("falha ao buscar o histórico deixa o chat vazio", async () => {
    mockedFetchSnapshot.mockResolvedValue(null);

    render(<ChatWidget />);

    await waitFor(() => expect(mockedFetchSnapshot).toHaveBeenCalled());
    expect(useChatStore.getState().messages).toEqual([]);
  });

  it("captura o status de atendimento humano já ao montar, sem esperar o envio de mensagem", async () => {
    mockedFetchSnapshot.mockResolvedValue({ status: "em_atendimento_humano", messages: [] });

    render(<ChatWidget />);

    await waitFor(() =>
      expect(useChatStore.getState().humanAttendanceStatus).toBe("em_atendimento_humano"),
    );
  });
});
