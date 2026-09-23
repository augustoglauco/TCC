"use client";

import { useEffect, useRef, useState } from "react";

import AudioRecorder from "@/components/chat/AudioRecorder";
import ImageUploader from "@/components/chat/ImageUploader";
import MessageBubble from "@/components/chat/MessageBubble";
import { Modal } from "@/components/ui/Modal";
import { sendChatMessage } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";

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

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [pendingImage, setPendingImage] = useState<{ base64: string; name: string } | null>(null);
  const [error, setError] = useState<PendingError | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
    }
  }, [messages, error, open]);

  const hasAssistantMessages = messages.some((m) => m.role === "assistant");

  async function submitMessage(text: string, overrideImage?: { base64: string; name: string } | null) {
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

    addMessage({ id: crypto.randomUUID(), role: "user", text: userText });
    setInput("");
    setIsSending(true);
    setError(null);

    const assistantId = crypto.randomUUID();
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
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: () => {},
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
          metrics: {
            modelName: data.model_name ?? undefined,
            promptTokens: data.prompt_tokens ?? undefined,
            completionTokens: data.completion_tokens ?? undefined,
            latencyMs: data.latency_ms ?? undefined,
            ttftMs: data.ttft_ms ?? undefined,
            tps: data.tps ?? undefined,
            confidence: data.confidence ?? undefined,
            complexity: data.complexity ?? undefined,
            estimatedCostUsd: data.estimated_cost_usd ?? undefined,
            ragRetrievalMs: data.rag_retrieval_ms ?? undefined,
            ragChunksCount: data.rag_chunks_count ?? undefined,
            ragAvgScore: data.rag_avg_score ?? undefined,
            ragChunks: data.rag_chunks ?? undefined,
            escalationReason: data.escalation_reason,
            routerProvider: data.router_provider ?? undefined,
          },
        });
      },
      onError: (msg) => {
        setError({ text: msg, retry: { message: trimmed, imageBase64: imageToSend?.base64, imageName: imageToSend?.name } });
      },
    });

    setIsSending(false);
  }

  async function submitAudio(audioBase64: string) {
    if (isSending) return;

    const pendingId = crypto.randomUUID();
    addMessage({ id: pendingId, role: "user", text: AUDIO_PENDING_TEXT });
    setIsSending(true);
    setError(null);

    const assistantId = crypto.randomUUID();
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
      conversationId: conversationId || undefined,
      onConversationId: (id) => setConversationId(id),
      onTranscription: (text) => {
        transcricaoRecebida = true;
        updateMessage(pendingId, { text: text || AUDIO_FALLBACK_TEXT });
      },
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
          metrics: {
            modelName: data.model_name ?? undefined,
            promptTokens: data.prompt_tokens ?? undefined,
            completionTokens: data.completion_tokens ?? undefined,
            latencyMs: data.latency_ms ?? undefined,
            ttftMs: data.ttft_ms ?? undefined,
            tps: data.tps ?? undefined,
            confidence: data.confidence ?? undefined,
            complexity: data.complexity ?? undefined,
            estimatedCostUsd: data.estimated_cost_usd ?? undefined,
            ragRetrievalMs: data.rag_retrieval_ms ?? undefined,
            ragChunksCount: data.rag_chunks_count ?? undefined,
            ragAvgScore: data.rag_avg_score ?? undefined,
            ragChunks: data.rag_chunks ?? undefined,
            escalationReason: data.escalation_reason,
            routerProvider: data.router_provider ?? undefined,
          },
        });
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

  const controlsDisabled = isSending || isRecording;
  const canSend = !controlsDisabled && (!!input.trim() || !!pendingImage);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Chat com Agente Virtual"
      description="Assistente IA multimodal com métricas de inferência em tempo real"
      size="2xl"
    >
      <div className="flex h-[68vh] flex-col rounded-xl border border-slate-200 bg-slate-50/50">
        {hasAssistantMessages && (
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-100/80 px-4 py-2 text-xs">
            <span className="text-slate-600 font-medium flex items-center gap-1.5">
              📊 Métricas de Desempenho & Telemetria
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => exportMetricsToCsv(messages)}
                className="rounded bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-slate-800 transition-colors flex items-center gap-1"
              >
                📥 Exportar CSV
              </button>
              <button
                type="button"
                onClick={() => exportMetricsToJson(messages)}
                className="rounded bg-slate-200 px-2.5 py-1 text-[11px] font-semibold text-slate-800 hover:bg-slate-300 transition-colors flex items-center gap-1"
              >
                📥 Exportar JSON
              </button>
            </div>
          </div>
        )}

        <div aria-live="polite" className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-400">
              <span className="text-3xl">💬</span>
              <p className="text-sm font-medium">Envie uma mensagem ou grave um áudio para iniciar o atendimento.</p>
            </div>
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
          className="flex items-center gap-2 border-t border-slate-200 bg-white p-3 rounded-b-xl"
        >
          <label htmlFor="chat-modal-input" className="sr-only">
            Mensagem
          </label>
          {pendingImage && (
            <div className="flex items-center gap-1 rounded-lg border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700">
              <span>🖼️ {pendingImage.name}</span>
              <button
                type="button"
                onClick={() => setPendingImage(null)}
                className="ml-1 font-bold hover:text-blue-900"
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
            placeholder="Digite sua mensagem ou pergunte sobre nossos produtos..."
            className="flex-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-400/20 disabled:opacity-50"
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
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors shadow-2xs"
          >
            Enviar
          </button>
        </form>
      </div>
    </Modal>
  );
}
