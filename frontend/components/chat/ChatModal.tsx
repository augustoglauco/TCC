"use client";

import { useState } from "react";

import { ChatDragOverlay } from "@/components/chat/ChatDragOverlay";
import { ChatInputArea } from "@/components/chat/ChatInputArea";
import { ChatMensagens, WELCOME_MESSAGE } from "@/components/chat/ChatMensagens";
import { ChatMetricsBar } from "@/components/chat/ChatMetricsBar";
import { ChatModalTitulo } from "@/components/chat/ChatModalTitulo";
import { Modal } from "@/components/ui/Modal";
import { useChatAcoes } from "@/lib/hooks/useChatAcoes";
import { useChatDropZone } from "@/lib/hooks/useChatDropZone";
import { type PendingImage, useChatEnvio } from "@/lib/hooks/useChatEnvio";
import { useChatFoco } from "@/lib/hooks/useChatFoco";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useConversaHumanaPolling } from "@/lib/hooks/useConversaHumanaPolling";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";

export { WELCOME_MESSAGE };

export interface ChatModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChatModal({ open, onOpenChange }: ChatModalProps) {
  const messages = useChatStore((state) => state.messages);
  const conversationId = useChatStore((state) => state.conversationId);
  const pendingInput = useChatStore((state) => state.pendingInput);

  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [pendingImage, setPendingImage] = useState<PendingImage | null>(null);

  const {
    isSending,
    error,
    setError,
    escalonamento,
    setEscalonamento,
    submitMessage,
    submitAudio,
    handleRetry,
  } = useChatEnvio({ conversationId, pendingImage, setPendingImage, setInput });

  const { handleClearHistory, handleCloseConversation, handleSolicitarAtendente } = useChatAcoes({
    conversationId,
    onOpenChange,
    onHistoricoApagado: () => {
      setError(null);
      setEscalonamento(null);
    },
  });

  const controlsDisabled = isSending || isRecording;
  const canSend = !controlsDisabled && (!!input.trim() || !!pendingImage);

  const { isDraggingOver, handleDragOver, handleDragLeave, handleDrop } = useChatDropZone({
    disabled: controlsDisabled,
    onImage: (base64, name) => setPendingImage({ base64, name }),
    onAudio: (base64) => void submitAudio(base64),
    onError: (text) => setError({ text, retry: {} }),
  });

  useConversaHumanaPolling(open, conversationId);

  const { messagesEndRef, inputRef, focarCaixaMensagem, focarCaixaMensagemSePonteiroPreciso } =
    useChatFoco({ open, controlsDisabled, messages, error, pendingInput, setInput });

  // Executa a ação e devolve o foco à caixa de mensagem (só com ponteiro preciso).
  const comFoco = (acao: () => void) => () => {
    acao();
    focarCaixaMensagemSePonteiroPreciso();
  };

  const hasAssistantMessages = messages.some((m) => m.role === "assistant");

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={<ChatModalTitulo />}
      description="Assistente IA multimodal com métricas de inferência em tempo real"
      size="2xl"
    >
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="relative flex h-[62vh] sm:h-[68vh] min-h-[380px] max-h-[600px] flex-col rounded-xl border border-slate-200 bg-slate-50/50"
      >
        <ChatDragOverlay visible={isDraggingOver} />
        {hasAssistantMessages && (
          <ChatMetricsBar
            onExportCsv={comFoco(() => exportMetricsToCsv(messages))}
            onExportJson={comFoco(() => exportMetricsToJson(messages))}
          />
        )}

        <ChatMensagens
          messages={messages}
          escalonamento={escalonamento}
          erroTexto={error ? error.text : null}
          messagesEndRef={messagesEndRef}
          onDismissEscalonamento={comFoco(() => setEscalonamento(null))}
          onRetry={comFoco(handleRetry)}
        />

        <ChatInputArea
          input={input}
          pendingImage={pendingImage}
          controlsDisabled={controlsDisabled}
          isSending={isSending}
          canSend={canSend}
          showActions={messages.length > 0}
          onInputChange={setInput}
          onRemovePendingImage={() => {
            setPendingImage(null);
            focarCaixaMensagem();
          }}
          onSubmit={(e) => {
            e.preventDefault();
            void submitMessage(input);
          }}
          onImageSelected={(base64, name) => {
            setPendingImage({ base64, name });
            focarCaixaMensagem();
          }}
          onRecordingComplete={(audioBase64) => void submitAudio(audioBase64)}
          onRecordingStateChange={setIsRecording}
          onSolicitarAtendente={comFoco(() => void handleSolicitarAtendente())}
          onEncerrar={comFoco(() => void handleCloseConversation())}
          onLimparHistorico={comFoco(() => void handleClearHistory())}
          inputRef={inputRef}
        />
      </div>
    </Modal>
  );
}
