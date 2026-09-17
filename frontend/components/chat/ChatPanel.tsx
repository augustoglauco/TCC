"use client";

import { useState } from "react";

import { ChatApiError, sendChatMessage } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";

import AudioRecorder from "./AudioRecorder";
import MessageBubble from "./MessageBubble";

interface PendingRetry {
  message?: string;
  audioBase64?: string;
}

interface PendingError {
  text: string;
  retry: PendingRetry;
}

// MVP: só deveria aparecer se o backend retornasse 200 com
// `transcribed_message: null` para um envio de áudio puro, o que o contrato
// atual não permite (nesse caso ele responde 422 antes) — mantido como rede
// de segurança defensiva (ver docs/FRONTEND.md §4).
const AUDIO_FALLBACK_TEXT = "(áudio sem fala reconhecível)";
const AUDIO_PENDING_TEXT = "🎤 Transcrevendo áudio...";
const AUDIO_FAILED_TEXT = "🎤 (não foi possível processar o áudio)";

export default function ChatPanel() {
  const messages = useChatStore((state) => state.messages);
  const conversationId = useChatStore((state) => state.conversationId);
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const setConversationId = useChatStore((state) => state.setConversationId);

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<PendingError | null>(null);

  async function submitMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isSending) {
      return;
    }

    addMessage({ id: crypto.randomUUID(), role: "user", text: trimmed });
    setInput("");
    setIsSending(true);
    setError(null);

    try {
      const response = await sendChatMessage({
        message: trimmed,
        conversationId: conversationId || undefined,
      });
      setConversationId(response.conversation_id);
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        text: response.message,
        domain: response.domain,
        backendUsed: response.backend_used,
      });
    } catch (caught) {
      const message =
        caught instanceof ChatApiError ? caught.message : "Erro inesperado. Tente novamente.";
      setError({ text: message, retry: { message: trimmed } });
    } finally {
      setIsSending(false);
    }
  }

  async function submitAudio(audioBase64: string) {
    if (isSending) {
      return;
    }

    // Bolha otimista: o cliente não sabe o que foi dito até a resposta
    // voltar (só o backend transcreve), mas precisa mostrar *algo* na hora —
    // sem isso, um erro depois deixava a mensagem de áudio sem nenhum
    // vestígio na conversa (ver docs/FRONTEND.md §3/§4).
    const pendingId = crypto.randomUUID();
    addMessage({ id: pendingId, role: "user", text: AUDIO_PENDING_TEXT });
    setIsSending(true);
    setError(null);

    try {
      const response = await sendChatMessage({
        audioBase64,
        conversationId: conversationId || undefined,
      });
      setConversationId(response.conversation_id);
      updateMessage(pendingId, { text: response.transcribed_message ?? AUDIO_FALLBACK_TEXT });
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        text: response.message,
        domain: response.domain,
        backendUsed: response.backend_used,
      });
    } catch (caught) {
      const message =
        caught instanceof ChatApiError ? caught.message : "Erro inesperado. Tente novamente.";
      updateMessage(pendingId, { text: AUDIO_FAILED_TEXT });
      setError({ text: message, retry: { audioBase64 } });
    } finally {
      setIsSending(false);
    }
  }

  function handleRetry() {
    if (!error) {
      return;
    }
    const { retry } = error;
    setError(null);
    if (retry.audioBase64) {
      void submitAudio(retry.audioBase64);
    } else if (retry.message) {
      void submitMessage(retry.message);
    }
  }

  const toggleOpen = useChatStore((state) => state.toggleOpen);
  const controlsDisabled = isSending || isRecording;

  return (
    <div className="fixed inset-x-3 bottom-20 top-auto z-50 flex h-[80vh] max-h-[540px] flex-col rounded-xl border border-slate-200 bg-white shadow-2xl sm:static sm:h-[32rem] sm:w-96">
      <header className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-4 py-3 rounded-t-xl">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <h2 className="text-sm font-bold text-slate-900">Assistente Virtual</h2>
        </div>
        <button
          type="button"
          onClick={toggleOpen}
          aria-label="Fechar painel de chat"
          className="flex h-7 w-7 items-center justify-center rounded-md text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
        >
          ✕
        </button>
      </header>

      <div aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && (
          <p className="text-sm text-gray-500">Envie uma mensagem para começar a conversa.</p>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {error && (
          <div
            role="alert"
            data-testid="chat-error"
            className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            <p>{error.text}</p>
            <button
              type="button"
              onClick={handleRetry}
              className="mt-1 font-medium underline hover:no-underline"
            >
              Tentar novamente
            </button>
          </div>
        )}
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submitMessage(input);
        }}
        className="flex gap-2 border-t border-gray-200 p-3"
      >
        <label htmlFor="chat-input" className="sr-only">
          Mensagem
        </label>
        <input
          id="chat-input"
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={controlsDisabled}
          placeholder="Digite sua mensagem..."
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
        />
        <AudioRecorder
          disabled={isSending}
          onRecordingComplete={(audioBase64) => void submitAudio(audioBase64)}
          onRecordingStateChange={setIsRecording}
        />
        <button
          type="submit"
          disabled={controlsDisabled || !input.trim()}
          className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
