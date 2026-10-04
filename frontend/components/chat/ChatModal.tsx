"use client";

import { useEffect, useRef, useState } from "react";

import AudioRecorder from "@/components/chat/AudioRecorder";
import EscalonamentoBanner from "@/components/chat/EscalonamentoBanner";
import ImageUploader from "@/components/chat/ImageUploader";
import MessageBubble from "@/components/chat/MessageBubble";
import { Modal } from "@/components/ui/Modal";
import { closeConversation, deleteConversation, sendChatMessage } from "@/lib/api/chat";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import type { ChatEscalonamentoData } from "@/lib/types/chat";
import { metricsFromDone } from "@/lib/utils/chatMetrics";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";
import { fileToBase64 } from "@/lib/utils/fileToBase64";
import { generateId } from "@/lib/utils/generateId";

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

interface PendingRetry {
  message?: string;
  audioBase64?: string;
  imageBase64?: string;
  imageName?: string;
}

interface PendingError {
  text: string;
  retry: PendingRetry;
}

const AUDIO_FALLBACK_TEXT = "(áudio sem fala reconhecível)";
const AUDIO_PENDING_TEXT = "🎤 Transcrevendo áudio...";
const AUDIO_FAILED_TEXT = "🎤 (não foi possível processar o áudio)";
const NO_RESPONSE_TEXT = "(sem resposta do modelo, tente novamente)";

export interface ChatModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChatModal({ open, onOpenChange }: ChatModalProps) {
  const messages = useChatStore((state) => state.messages);
  const conversationId = useChatStore((state) => state.conversationId);
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const setConversationId = useChatStore((state) => state.setConversationId);
  const clearChat = useChatStore((state) => state.clearChat);

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [pendingImage, setPendingImage] = useState<{ base64: string; name: string } | null>(null);
  const [error, setError] = useState<PendingError | null>(null);
  const [escalonamento, setEscalonamento] = useState<ChatEscalonamentoData | null>(null);
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  async function handleClearHistory() {
    if (
      typeof window !== "undefined" &&
      !window.confirm("Deseja apagar todo o histórico e a memória desta conversa no servidor?")
    ) {
      return;
    }
    await deleteConversation(conversationId);
    clearChat();
    setError(null);
    setEscalonamento(null);
  }

  async function handleCloseConversation() {
    if (
      typeof window !== "undefined" &&
      !window.confirm("Deseja finalizar este atendimento? A sessão será registrada como encerrada.")
    ) {
      return;
    }
    await closeConversation(conversationId, "manual_usuario");
    addMessage({
      id: generateId(),
      role: "assistant",
      text: "🏁 Atendimento encerrado. Obrigado pelo contato!",
    });
    setConversationId(generateId());
  }

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const pendingInput = useChatStore((state) => state.pendingInput);

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
      if (pendingInput) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setInput(pendingInput);
        useChatStore.setState({ pendingInput: null });
      }
    }
  }, [messages, error, open, pendingInput]);

  const hasAssistantMessages = messages.some((m) => m.role === "assistant");

  async function submitMessage(
    text: string,
    overrideImage?: { base64: string; name: string } | null,
  ) {
    const trimmed = text.trim();
    // `overrideImage` é usado pelo retry para passar a imagem diretamente,
    // sem depender do estado React (que ainda não teria sido atualizado pelo
    // setPendingImage chamado logo antes no handleRetry).
    const imageToSend = overrideImage !== undefined ? overrideImage : pendingImage;
    if (!trimmed && !imageToSend) return;
    if (isSending) return;

    setPendingImage(null);

    const userText = trimmed
      ? imageToSend
        ? `${trimmed} [🖼️ ${imageToSend.name}]`
        : trimmed
      : `[🖼️ ${imageToSend!.name}]`;

    addMessage({ id: generateId(), role: "user", text: userText });
    setInput("");
    setIsSending(true);
    setError(null);

    const assistantId = generateId();
    let bolhaCriada = false;
    let textoAcumulado = "";

    function garantirBolha(textoInicial: string) {
      if (!bolhaCriada) {
        bolhaCriada = true;
        addMessage({ id: assistantId, role: "assistant", text: textoInicial });
      } else {
        updateMessage(assistantId, { text: textoInicial });
      }
    }

    await sendChatMessage({
      message: trimmed || undefined,
      imageBase64: imageToSend?.base64,
      userEmail: useAuthStore.getState().user?.email,
      authToken: useAuthStore.getState().token,
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: () => {},
      onEscalonamento: (data) => setEscalonamento(data),
      onStatus: (status) => {
        if (status === "carregando_modelo") {
          garantirBolha("🤖 Aguarde, consultando documentos internos...");
        }
      },
      onToken: (chunk) => {
        textoAcumulado += chunk;
        garantirBolha(textoAcumulado);
      },
      onDone: (data) => {
        // MVP: garante que a bolha nunca fique travada mostrando o
        // placeholder de status (ou vazia) quando a geração produz zero
        // tokens — ex. logo após um cold-start do modelo local.
        garantirBolha(textoAcumulado || NO_RESPONSE_TEXT);
        updateMessage(assistantId, {
          domain: data.domain,
          backendUsed: data.backend_used,
          metrics: metricsFromDone(data),
          card: data.card ?? undefined,
        });
        if (data.card?.tipo === "grafico" && typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("refresh_admin_charts"));
        }
      },
      onError: (msg) => {
        setError({
          text: msg,
          retry: {
            message: trimmed,
            imageBase64: imageToSend?.base64,
            imageName: imageToSend?.name,
          },
        });
      },
    });

    setIsSending(false);
  }

  async function submitAudio(audioBase64: string) {
    if (isSending) return;

    const pendingId = generateId();
    addMessage({ id: pendingId, role: "user", text: AUDIO_PENDING_TEXT });
    setIsSending(true);
    setError(null);

    const assistantId = generateId();
    let bolhaCriada = false;
    let textoAcumulado = "";
    let transcricaoRecebida = false;

    function garantirBolha(textoInicial: string) {
      if (!bolhaCriada) {
        bolhaCriada = true;
        addMessage({ id: assistantId, role: "assistant", text: textoInicial });
      } else {
        updateMessage(assistantId, { text: textoInicial });
      }
    }

    await sendChatMessage({
      audioBase64,
      userEmail: useAuthStore.getState().user?.email,
      authToken: useAuthStore.getState().token,
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: (text) => {
        transcricaoRecebida = true;
        updateMessage(pendingId, { text: text || AUDIO_FALLBACK_TEXT });
      },
      onEscalonamento: (data) => setEscalonamento(data),
      onStatus: (status) => {
        if (status === "carregando_modelo") {
          garantirBolha("🤖 Aguarde, consultando documentos internos...");
        }
      },
      onToken: (chunk) => {
        textoAcumulado += chunk;
        garantirBolha(textoAcumulado);
      },
      onDone: (data) => {
        // MVP: mesma garantia do fluxo de texto — nunca deixa a bolha do
        // assistente travada no placeholder de status (ou vazia) quando a
        // geração produz zero tokens.
        garantirBolha(textoAcumulado || NO_RESPONSE_TEXT);
        updateMessage(assistantId, {
          domain: data.domain,
          backendUsed: data.backend_used,
          metrics: metricsFromDone(data),
          card: data.card ?? undefined,
        });
        if (data.card?.tipo === "grafico" && typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("refresh_admin_charts"));
        }
      },
      onError: (msg) => {
        if (!transcricaoRecebida) {
          updateMessage(pendingId, { text: AUDIO_FAILED_TEXT });
        }
        setError({ text: msg, retry: { audioBase64 } });
      },
    });

    setIsSending(false);
  }

  function handleRetry() {
    if (!error) return;
    const { retry } = error;
    setError(null);
    if (retry.audioBase64) {
      void submitAudio(retry.audioBase64);
    } else {
      // Passa a imagem diretamente para submitMessage em vez de chamar
      // setPendingImage antes — setState é assíncrono e o estado ainda seria
      // null quando submitMessage lesse pendingImage no mesmo ciclo de render.
      const img =
        retry.imageBase64 && retry.imageName
          ? { base64: retry.imageBase64, name: retry.imageName }
          : null;
      void submitMessage(retry.message ?? "", img);
    }
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (!isDraggingOver) setIsDraggingOver(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDraggingOver(false);
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    if (controlsDisabled) return;

    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const isImage = file.type.startsWith("image/");
    const isAudio =
      file.type.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|webm|aac|flac)$/i.test(file.name);

    try {
      if (isImage) {
        const base64 = await fileToBase64(file);
        setPendingImage({ base64, name: file.name });
      } else if (isAudio) {
        const base64 = await fileToBase64(file);
        void submitAudio(base64);
      } else {
        setError({
          text: "Formato de arquivo não suportado. Por favor, envie imagens (PNG, JPG, WEBP) ou áudios.",
          retry: {},
        });
      }
    } catch {
      setError({
        text: "Erro ao processar o arquivo arrastado. Tente novamente.",
        retry: {},
      });
    }
  }

  const controlsDisabled = isSending || isRecording;
  const canSend = !controlsDisabled && (!!input.trim() || !!pendingImage);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Chat com Agente Virtual"
      description="Assistente IA multimodal com métricas de inferência em tempo real"
      size="2xl"
      headerActions={
        messages.length > 0 && (
          <div className="flex items-center gap-1.5 sm:gap-2">
            <button
              type="button"
              onClick={() => void handleCloseConversation()}
              className="flex items-center gap-1 rounded-lg border border-amber-300 bg-amber-50 px-2 sm:px-2.5 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-100 transition-colors"
              title="Encerrar atendimento atual e contabilizar métricas"
              aria-label="Encerrar atendimento"
            >
              <span>🏁</span>
              <span className="hidden sm:inline">Encerrar atendimento</span>
            </button>
            <button
              type="button"
              onClick={() => void handleClearHistory()}
              className="flex items-center gap-1 rounded-lg border border-red-200 bg-red-50 px-2 sm:px-2.5 py-1 text-xs font-semibold text-red-600 hover:bg-red-100 transition-colors"
              title="Apagar mensagens e memória da conversa"
              aria-label="Limpar histórico da conversa"
            >
              <span>🗑️</span>
              <span className="hidden sm:inline">Limpar conversa</span>
            </button>
          </div>
        )
      }
    >
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="relative flex h-[62vh] sm:h-[68vh] min-h-[380px] max-h-[600px] flex-col rounded-xl border border-slate-200 bg-slate-50/50"
      >
        {isDraggingOver && (
          <div
            data-testid="chat-drag-overlay"
            className="absolute inset-0 z-50 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-blue-500 bg-blue-50/95 p-6 text-center backdrop-blur-xs transition-all"
          >
            <div className="rounded-full bg-blue-100 p-4 text-3xl shadow-xs">📥</div>
            <p className="mt-3 text-sm font-semibold text-blue-900">
              Solte a imagem ou áudio aqui para enviar
            </p>
            <p className="mt-1 text-xs text-blue-600">
              Suporta imagens (PNG, JPG, WEBP) e arquivos de áudio (MP3, WAV, M4A, etc.)
            </p>
          </div>
        )}
        {hasAssistantMessages && (
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100/80 px-2.5 sm:px-4 py-1.5 sm:py-2 text-xs shrink-0">
            <span className="text-slate-600 font-medium flex items-center gap-1 text-[11px] sm:text-xs">
              📊 <span className="hidden sm:inline">Métricas de Desempenho & Telemetria</span>
              <span className="sm:hidden">Telemetria</span>
            </span>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <button
                type="button"
                onClick={() => exportMetricsToCsv(messages)}
                className="rounded bg-slate-900 px-2 sm:px-2.5 py-1 text-[10px] sm:text-[11px] font-semibold text-white hover:bg-slate-800 transition-colors flex items-center gap-1"
              >
                📥 <span className="hidden xs:inline">Exportar </span>CSV
              </button>
              <button
                type="button"
                onClick={() => exportMetricsToJson(messages)}
                className="rounded bg-slate-200 px-2 sm:px-2.5 py-1 text-[10px] sm:text-[11px] font-semibold text-slate-800 hover:bg-slate-300 transition-colors flex items-center gap-1"
              >
                📥 <span className="hidden xs:inline">Exportar </span>JSON
              </button>
            </div>
          </div>
        )}

        <div
          aria-live="polite"
          className="flex-1 space-y-3 sm:space-y-4 overflow-y-auto p-2.5 sm:p-4"
        >
          <EscalonamentoBanner
            escalonamento={escalonamento}
            onDismiss={() => setEscalonamento(null)}
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
            <div
              role="alert"
              data-testid="chat-error"
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 shadow-2xs"
            >
              <p className="font-semibold">{error.text}</p>
              <button
                type="button"
                onClick={handleRetry}
                className="mt-1 font-bold underline hover:no-underline"
              >
                Tentar novamente
              </button>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submitMessage(input);
          }}
          className="flex items-center gap-1.5 sm:gap-2 border-t border-slate-200 bg-white p-2 sm:p-3 rounded-b-xl shrink-0"
        >
          <label htmlFor="chat-modal-input" className="sr-only">
            Mensagem
          </label>
          {pendingImage && (
            <div className="flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700 max-w-[120px] sm:max-w-none truncate">
              <span className="truncate">🖼️ {pendingImage.name}</span>
              <button
                type="button"
                onClick={() => setPendingImage(null)}
                className="ml-1 font-bold hover:text-blue-900 shrink-0"
                aria-label="Remover imagem"
              >
                ×
              </button>
            </div>
          )}
          <input
            id="chat-modal-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={controlsDisabled}
            placeholder="Digite sua mensagem..."
            className="flex-1 min-w-0 rounded-xl border border-slate-300 bg-slate-50 px-3 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-400/20 disabled:opacity-50"
          />
          <ImageUploader
            disabled={controlsDisabled}
            onImageSelected={(base64, name) => setPendingImage({ base64, name })}
          />
          <AudioRecorder
            disabled={isSending}
            onRecordingComplete={(audioBase64) => void submitAudio(audioBase64)}
            onRecordingStateChange={setIsRecording}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="rounded-xl bg-slate-900 px-3 sm:px-4 py-2 sm:py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors shadow-2xs shrink-0"
          >
            Enviar
          </button>
        </form>
      </div>
    </Modal>
  );
}
