"use client";

import { useState } from "react";

import { ChatApiError, sendChatMessage } from "@/lib/api/chat";
import { useChatStore } from "@/lib/hooks/useChatStore";

import MessageBubble from "./MessageBubble";

interface PendingError {
  text: string;
  retryMessage: string;
}

export default function ChatPanel() {
  const messages = useChatStore((state) => state.messages);
  const conversationId = useChatStore((state) => state.conversationId);
  const addMessage = useChatStore((state) => state.addMessage);
  const setConversationId = useChatStore((state) => state.setConversationId);

  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
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
      const response = await sendChatMessage(trimmed, conversationId || undefined);
      setConversationId(response.conversation_id);
      addMessage({
        id: crypto.randomUUID(),
        role: "assistant",
        text: response.message,
        domain: response.domain,
      });
    } catch (caught) {
      const message =
        caught instanceof ChatApiError ? caught.message : "Erro inesperado. Tente novamente.";
      setError({ text: message, retryMessage: trimmed });
    } finally {
      setIsSending(false);
    }
  }

  function handleRetry() {
    if (!error) {
      return;
    }
    const { retryMessage } = error;
    setError(null);
    void submitMessage(retryMessage);
  }

  return (
    <div className="flex h-[32rem] w-80 flex-col rounded-lg border border-gray-200 bg-white shadow-xl sm:w-96">
      <header className="border-b border-gray-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">Fale com a gente</h2>
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
          disabled={isSending}
          placeholder="Digite sua mensagem..."
          className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isSending || !input.trim()}
          className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Enviar
        </button>
      </form>
    </div>
  );
}
