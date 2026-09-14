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

// MVP: o comportamento de gravação em si (permissão, MediaRecorder) é
// testado isoladamente em `AudioRecorder.test.tsx`; aqui só precisamos de um
// jeito de disparar `onRecordingComplete` para testar a integração com o
// envio/exibição da resposta no painel.
vi.mock("@/components/chat/AudioRecorder", () => ({
  default: ({
    onRecordingComplete,
  }: {
    onRecordingComplete: (audioBase64: string) => void;
  }) => (
    <button type="button" onClick={() => onRecordingComplete("base64-audio-fake")}>
      Simular gravação de áudio
    </button>
  ),
}));

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
      transcribed_message: null,
    });

    render(<ChatPanel />);

    await user.type(screen.getByLabelText("Mensagem"), "Vocês têm o produto X?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Vocês têm o produto X?")).toBeInTheDocument();
    expect(await screen.findByText("Temos esse produto em estoque.")).toBeInTheDocument();
    expect(screen.getByTestId("message-domain-label")).toHaveTextContent("Vendas");
    expect(mockedSendChatMessage).toHaveBeenCalledWith({
      message: "Vocês têm o produto X?",
      conversationId: undefined,
    });
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
      transcribed_message: null,
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

  it("envia áudio gravado e exibe o texto transcrito na bolha do usuário", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      conversation_id: "conv-1",
      message: "Posso ajudar com seu agendamento.",
      domain: "agendamento",
      backend_used: "local",
      escalation_reason: "nenhum",
      transcribed_message: "Quero agendar uma visita",
    });

    render(<ChatPanel />);

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByText("Quero agendar uma visita")).toBeInTheDocument();
    expect(await screen.findByText("Posso ajudar com seu agendamento.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledWith({
      audioBase64: "base64-audio-fake",
      conversationId: undefined,
    });
  });

  it("usa texto de fallback quando a transcrição do áudio vem vazia (defensivo)", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockResolvedValueOnce({
      conversation_id: "conv-1",
      message: "Não entendi, pode repetir?",
      domain: "atendimento",
      backend_used: "local",
      escalation_reason: "nenhum",
      transcribed_message: null,
    });

    render(<ChatPanel />);

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByText("(áudio sem fala reconhecível)")).toBeInTheDocument();
  });

  it("permite tentar novamente o mesmo áudio após falha da API", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockRejectedValueOnce(
      new ChatApiError("Serviço temporariamente indisponível. Tente novamente.", 503),
    );
    mockedSendChatMessage.mockResolvedValueOnce({
      conversation_id: "conv-1",
      message: "Agora funcionou.",
      domain: "suporte",
      backend_used: "local",
      escalation_reason: "nenhum",
      transcribed_message: "Preciso de suporte",
    });

    render(<ChatPanel />);

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Serviço temporariamente indisponível. Tente novamente.",
    );

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(await screen.findByText("Preciso de suporte")).toBeInTheDocument();
    expect(await screen.findByText("Agora funcionou.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
    expect(mockedSendChatMessage).toHaveBeenNthCalledWith(2, {
      audioBase64: "base64-audio-fake",
      conversationId: undefined,
    });
  });
});
