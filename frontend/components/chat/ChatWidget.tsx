"use client";

import { useEffect } from "react";

import { getOrCreateConversationId, useChatStore } from "@/lib/hooks/useChatStore";

import ChatPanel from "./ChatPanel";

/**
 * Botão flutuante (canto inferior direito) que abre/fecha o painel de chat.
 * Presente em todas as rotas via `app/layout.tsx`.
 *
 * MVP: texto e áudio (via `AudioRecorder`), resposta síncrona — sem upload de
 * imagem, sem streaming (SSE), sem cards ricos e sem banner de transferência
 * humana (ver docs/FRONTEND.md §3, itens pendentes da Fase 8).
 */
export default function ChatWidget() {
  const isOpen = useChatStore((state) => state.isOpen);
  const toggleOpen = useChatStore((state) => state.toggleOpen);
  const conversationId = useChatStore((state) => state.conversationId);
  const setConversationId = useChatStore((state) => state.setConversationId);

  useEffect(() => {
    if (!conversationId) {
      setConversationId(getOrCreateConversationId());
    }
  }, [conversationId, setConversationId]);

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-3">
      {isOpen && <ChatPanel />}
      <button
        type="button"
        onClick={toggleOpen}
        aria-expanded={isOpen}
        aria-label={isOpen ? "Fechar chat" : "Abrir chat"}
        className="flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-2xl text-white shadow-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-400"
      >
        {isOpen ? "✕" : "💬"}
      </button>
    </div>
  );
}
