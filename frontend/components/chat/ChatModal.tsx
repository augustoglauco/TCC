"use client";

import { useState } from "react";

import { ChatDragOverlay } from "@/components/chat/ChatDragOverlay";
import { ChatErroAlerta } from "@/components/chat/ChatErroAlerta";
import { ChatInputArea } from "@/components/chat/ChatInputArea";
import { ChatMetricsBar } from "@/components/chat/ChatMetricsBar";
import { ChatModalTitulo } from "@/components/chat/ChatModalTitulo";
import EscalonamentoBanner from "@/components/chat/EscalonamentoBanner";
import MessageBubble from "@/components/chat/MessageBubble";
import { Modal } from "@/components/ui/Modal";
import { useChatAcoes } from "@/lib/hooks/useChatAcoes";
import { useChatDropZone } from "@/lib/hooks/useChatDropZone";
import { type PendingImage, useChatEnvio } from "@/lib/hooks/useChatEnvio";
import { useChatFoco } from "@/lib/hooks/useChatFoco";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useConversaHumanaPolling } from "@/lib/hooks/useConversaHumanaPolling";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";

/**
 * Mensagem de boas-vindas mostrada com a conversa vazia. Convida a informar o
 * e-mail junto com a pergunta (opcional): com ele o backend identifica o
 * cadastro e as compras do visitante (R10, classificação do usuário).
 */
export const WELCOME_MESSAGE =
  "Olá! 👋 Sou o assistente virtual da empresa. Posso ajudar com produtos e " +
  "orçamentos, suporte técnico, atendimento (nota fiscal, trocas) e agendamento " +
  "de visitas.\n\n" +
  "Se quiser, informe seu e-mail junto com a sua pergunta. Com ele identificamos " +
  "o seu cadastro e o seu histórico de compras, o que facilita o atendimento e o " +
  "nosso relacionamento com você. É opcional: você pode conversar normalmente " +
  "sem informá-lo. Pode escrever ou gravar um áudio.";

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
            onExportCsv={() => {
              exportMetricsToCsv(messages);
              focarCaixaMensagemSePonteiroPreciso();
            }}
            onExportJson={() => {
              exportMetricsToJson(messages);
              focarCaixaMensagemSePonteiroPreciso();
            }}
          />
        )}

        <div
          aria-live="polite"
          className="flex-1 space-y-3 sm:space-y-4 overflow-y-auto p-2.5 sm:p-4"
        >
          <EscalonamentoBanner
            escalonamento={escalonamento}
            onDismiss={() => {
              setEscalonamento(null);
              focarCaixaMensagemSePonteiroPreciso();
            }}
          />
          {messages.length === 0 && (
            // Boas-vindas só de interface (R10): não entra no store nem no
            // banco, e some quando chega a primeira mensagem ou o histórico.
            <MessageBubble
              message={{ id: "boas-vindas", role: "assistant", text: WELCOME_MESSAGE }}
            />
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {error && (
            <ChatErroAlerta
              texto={error.text}
              onRetry={() => {
                handleRetry();
                focarCaixaMensagemSePonteiroPreciso();
              }}
            />
          )}
          <div ref={messagesEndRef} />
        </div>

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
          onSolicitarAtendente={() => {
            void handleSolicitarAtendente();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          onEncerrar={() => {
            void handleCloseConversation();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          onLimparHistorico={() => {
            void handleClearHistory();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          inputRef={inputRef}
        />
      </div>
    </Modal>
  );
}
