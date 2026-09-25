import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatModal, WELCOME_MESSAGE } from "@/components/chat/ChatModal";
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
  default: ({ onRecordingComplete }: { onRecordingComplete: (audioBase64: string) => void }) => (
    <button type="button" onClick={() => onRecordingComplete("base64-audio-fake")}>
      Simular gravação de áudio
    </button>
  ),
}));

// Mock do ImageUploader: expõe um botão que dispara onImageSelected com
// dados determinísticos — o comportamento real do FileReader é testado
// isoladamente em ImageUploader.test.tsx.
vi.mock("@/components/chat/ImageUploader", () => ({
  default: ({
    onImageSelected,
    disabled,
  }: {
    onImageSelected: (base64: string, name: string) => void;
    disabled?: boolean;
  }) => (
    <button
      type="button"
      disabled={disabled}
      onClick={() => onImageSelected("base64-imagem-fake", "produto.png")}
    >
      Simular upload de imagem
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

  it("conversa vazia mostra a boas-vindas com o convite opcional para o e-mail", () => {
    renderModal();

    const boasVindas = screen.getByText(/Sou o assistente virtual da empresa/);
    expect(boasVindas).toHaveTextContent("informe seu e-mail junto com a sua pergunta");
    expect(boasVindas).toHaveTextContent("É opcional");
    // Só de interface: não vira mensagem da conversa.
    expect(useChatStore.getState().messages).toEqual([]);
    // Sem domínio, sem painel de métricas.
    expect(screen.queryByRole("button", { name: "Mostrar métricas da resposta" })).toBeNull();
  });

  it("boas-vindas some quando a conversa tem mensagens", () => {
    useChatStore.setState({ messages: [{ id: "m1", role: "user", text: "oi" }] });

    renderModal();

    expect(screen.queryByText(/Sou o assistente virtual da empresa/)).toBeNull();
    expect(WELCOME_MESSAGE).toContain("e-mail");
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

  it("propaga o provedor do roteador para o painel de métricas", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Resposta via Jev.");
      onDone({
        domain: "vendas",
        backend_used: "local",
        escalation_reason: "nenhum",
        router_provider: "jev_openrouter",
      });
    });

    renderModal();

    await user.type(screen.getByLabelText("Mensagem"), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Resposta via Jev.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mostrar métricas da resposta" }));

    expect(screen.getByText("TypeSafe Jev (OpenRouter)")).toBeInTheDocument();
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
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Olá");
      onToken(", tudo bem?");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

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

    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Resposta 1");
      onToken(" Resposta 2");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    const user = userEvent.setup();
    renderModal();

    await user.type(screen.getByLabelText("Mensagem"), "oi");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText("Resposta 1 Resposta 2")).toBeInTheDocument();
    expect(scrollIntoViewMock).toHaveBeenCalled();
  });

  // --- Fluxo de imagem (R6, Fase 3) ---

  it("selecionar imagem exibe badge com nome do arquivo e habilita Enviar", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));

    expect(screen.getByText(/produto\.png/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar" })).not.toBeDisabled();
  });

  it("botão × remove a imagem pendente e desabilita Enviar (sem texto)", async () => {
    const user = userEvent.setup();
    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    expect(screen.getByText(/produto\.png/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remover imagem" }));

    expect(screen.queryByText(/produto\.png/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
  });

  it("envia imagem e exibe bolha com nome do arquivo", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Produto encontrado.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByText(/produto\.png/)).toBeInTheDocument();
    expect(await screen.findByText("Produto encontrado.")).toBeInTheDocument();
    expect(mockedSendChatMessage).toHaveBeenCalledWith(
      expect.objectContaining({ imageBase64: "base64-imagem-fake" }),
    );
  });

  it("envia texto + imagem juntos", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Entendido.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    await user.type(screen.getByLabelText("Mensagem"), "O que é isso?");
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(mockedSendChatMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "O que é isso?",
        imageBase64: "base64-imagem-fake",
      }),
    );
  });

  it("badge de imagem é removido após o envio", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementation(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Ok.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    expect(screen.getByText(/produto\.png/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Enviar" }));

    await waitFor(() => {
      // Após o envio, o badge do form deve sumir (a bolha do usuário ainda
      // mostra o nome, mas o badge de "pendente" no input deve desaparecer).
      const badges = screen.queryAllByText(/produto\.png/);
      // Só a bolha do usuário deve restar, não o badge do form.
      expect(badges.length).toBeLessThanOrEqual(1);
    });
  });

  it("retry de imagem reenvia a imagem corretamente (bug #1 — regressão)", async () => {
    const user = userEvent.setup();
    // Primeira chamada: falha.
    mockedSendChatMessage.mockImplementationOnce(async ({ onError }) => {
      onError("Serviço indisponível.");
    });
    // Segunda chamada: sucesso.
    mockedSendChatMessage.mockImplementationOnce(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Produto encontrado.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Serviço indisponível.");

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    // O retry deve reenviar a imagem — sem o fix do bug #1, imageBase64
    // seria undefined na segunda chamada.
    await waitFor(() => {
      expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
    });
    expect(mockedSendChatMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ imageBase64: "base64-imagem-fake" }),
    );
    expect(await screen.findByText("Produto encontrado.")).toBeInTheDocument();
  });

  it("retry de só-imagem (sem texto) reenvia a imagem corretamente (bug #1 — regressão)", async () => {
    const user = userEvent.setup();
    mockedSendChatMessage.mockImplementationOnce(async ({ onError }) => {
      onError("Serviço indisponível.");
    });
    mockedSendChatMessage.mockImplementationOnce(async ({ onConversationId, onToken, onDone }) => {
      onConversationId("conv-1");
      onToken("Ok.");
      onDone({ domain: "vendas", backend_used: "local", escalation_reason: "nenhum" });
    });

    renderModal();

    // Só imagem, sem texto digitado.
    await user.click(screen.getByRole("button", { name: "Simular upload de imagem" }));
    await user.click(screen.getByRole("button", { name: "Enviar" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Tentar novamente" }));

    // Sem o fix, submitMessage retornava cedo (pendingImage era null) e
    // sendChatMessage nunca era chamado uma segunda vez.
    await waitFor(() => {
      expect(mockedSendChatMessage).toHaveBeenCalledTimes(2);
    });
    expect(mockedSendChatMessage).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ imageBase64: "base64-imagem-fake" }),
    );
  });
});
