"use client";

import { useState } from "react";

import AudioRecorder from "@/components/chat/AudioRecorder";
import MessageBubble from "@/components/chat/MessageBubble";
import { Modal } from "@/components/ui/Modal";
import { sendChatMessage } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";

interface PendingRetry {
  message?: string;
  audioBase64?: string;
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
  const [error, setError] = useState<PendingError | null>(null);

  const hasAssistantMessages = messages.some((m) => m.role === "assistant");

  async function submitMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isSending) return;

    addMessage({ id: crypto.randomUUID(), role: "user", text: trimmed });
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
      message: trimmed,
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
            escalationReason: data.escalation_reason,
          },
        });
      },
      onError: (msg) => {
        setError({ text: msg, retry: { message: trimmed } });
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
            escalationReason: data.escalation_reason,
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
    if (retry.audioBase64) void submitAudio(retry.audioBase64);
    else if (retry.message) void submitMessage(retry.message);
  }

  const controlsDisabled = isSending || isRecording;

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
          <input
            id="chat-modal-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={controlsDisabled}
            placeholder="Digite sua mensagem ou pergunte sobre nossos produtos..."
            className="flex-1 rounded-xl border border-slate-300 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-400/20 disabled:opacity-50"
          />
          <AudioRecorder
            disabled={isSending}
            onRecordingComplete={(audioBase64) => void submitAudio(audioBase64)}
            onRecordingStateChange={setIsRecording}
          />
          <button
            type="submit"
            disabled={controlsDisabled || !input.trim()}
            className="rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors shadow-2xs"
          >
            Enviar
          </button>
        </form>
      </div>
    </Modal>
  );
}
