import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatModal } from "@/components/chat/ChatModal";
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
// envio/exibição da resposta no modal.
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

function renderModal() {
  return render(<ChatModal open onOpenChange={vi.fn()} />);
}

describe("ChatModal", () => {
  beforeEach(() => {
    resetStore();
    mockedSendChatMessage.mockReset();
  });

  it("envia mensagem de texto e exibe a resposta do assistente", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Temos esse produto em estoque.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    await user.type(screen.getByLabelText("Mensagem"), "Vocês têm o produto X?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Vocês têm o produto X?")).toBeInTheDocument();
    expect(await screen.findByText("Temos esse produto em estoque.")).toBeInTheDocument();
    expect(screen.getByTestId("message-domain-label")).toHaveTextContent("Vendas");
    expect(mockedSendChatMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "Vocês têm o produto X?",
        conversationId: undefined,
      }),
    );
  });

  it("mostra bolha de erro com opção de tentar novamente e permite reenviar", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementationOnce(async ({ onError }) => {
      onError("Serviço temporariamente indisponível. Tente novamente.");
    });
    mockedSendChatMessage.mockImplementationOnce(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Tudo certo agora.");
      onDone({ domain: "suporte", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

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
    mockedSendChatMessage.mockImplementation(
      async ({ onConversationId, onTranscription, onToken, onDone }) => {
        onConversationId("conv-1");
        onTranscription("Quero agendar uma visita");
        onToken("Posso ajudar com seu agendamento.");
        onDone({ domain: "agendamento", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByText("Quero agendar uma visita")).toBeInTheDocument();
    expect(await screen.findByText("Posso ajudar com seu agendamento.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        audioBase64: "base64-audio-fake",
        conversationId: undefined,
      }),
    );
  });

  it("usa texto de fallback quando a transcrição do áudio vem vazia (defensivo)", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(
      async ({ onConversationId, onTranscription, onToken, onDone }) => {
        onConversationId("conv-1");
        onTranscription("");
        onToken("Não entendi, pode repetir?");
        onDone({ domain: "atendimento", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByText("(áudio sem fala reconhecível)")).toBeInTheDocument();
  });

  it("mantém uma bolha visível para o áudio mesmo quando a API falha (regressão)", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementationOnce(async ({ onError }) => {
      onError("Serviço temporariamente indisponível. Tente novamente.");
    });

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    // Antes da correção (em ChatPanel, precursor deste componente), uma
    // falha na API deixava a mensagem de áudio sem nenhum vestígio na
    // conversa — só a bolha de erro genérica aparecia.
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("🎤 (não foi possível processar o áudio)")).toBeInTheDocument();
  });

  it("permite tentar novamente o mesmo áudio após falha da API", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementationOnce(async ({ onError }) => {
      onError("Serviço temporariamente indisponível. Tente novamente.");
    });
    mockedSendChatMessage.mockImplementationOnce(
      async ({ onConversationId, onTranscription, onToken, onDone }) => {
        onConversationId("conv-1");
        onTranscription("Preciso de suporte");
        onToken("Agora funcionou.");
        onDone({ domain: "suporte", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular gravação de áudio" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Serviço temporariamente indisponível. Tente novamente.",
    );

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    expect(await screen.findByText("Preciso de suporte")).toBeInTheDocument();
    expect(await screen.findByText("Agora funcionou.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
    expect(mockedSendChatMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        audioBase64: "base64-audio-fake",
        conversationId: undefined,
      }),
    );
  });

  it("mostra o texto de status e substitui pelo primeiro token", async () => {
    // Controla manualmente quando `onToken` dispara (via uma Promise externa)
    // para conseguir observar o placeholder de status renderizado ANTES do
    // token chegar — não só o estado final da bolha.
    let liberarToken: () => void = () => {};
    const aguardaLiberacao = new Promise<void>((resolve) => {
      liberarToken = resolve;
    });

    mockedSendChatMessage.mockImplementation(
      async ({ onConversationId, onStatus, onToken, onDone }) => {
        onConversationId("conv-1");
        onStatus("carregando_modelo");
        await aguardaLiberacao;
        onToken("Resposta real.");
        onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByLabelText("Mensagem"), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/consultando documentos internos/)).toBeInTheDocument();

    liberarToken();

    expect(await screen.findByText("Resposta real.")).toBeInTheDocument();
    expect(screen.queryByText(/consultando documentos internos/)).not.toBeInTheDocument();
  });

  it("concatena múltiplos tokens na mesma bolha", async () => {
    mockedSendChatMessage.mockImplementation(
      async ({ onConversationId, onToken, onDone }) => {
        onConversationId("conv-1");
        onToken("Olá");
        onToken(", tudo bem?");
        onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    const user = userEvent.setup();
    renderModal();
    await user.type(screen.getByLabelText("Mensagem"), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Olá, tudo bem?")).toBeInTheDocument();
  });

  it("não renderiza o conteúdo quando `open` é false", () => {
    render(<ChatModal open={false} onOpenChange={vi.fn()} />);

    expect(screen.queryByLabelText("Mensagem")).not.toBeInTheDocument();
  });

  it("executa scrollIntoView para acompanhar o fluxo de mensagens", async () => {
    const scrollIntoViewMock = vi.fn();
    window.HTMLElement.prototype.scrollIntoView = scrollIntoViewMock;

    mockedSendChatMessage.mockImplementation(
      async ({ onConversationId, onToken, onDone }) => {
        onConversationId("conv-1");
        onToken("Resposta 1");
        onToken(" Resposta 2");
        onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
      },
    );

    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText("Mensagem"), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Resposta 1 Resposta 2")).toBeInTheDocument();
    expect(scrollIntoViewMock).toHaveBeenCalled();
  });
});
