"use client";

import { useEffect } from "react";

import { ChatModal } from "@/components/chat/ChatModal";
import { getOrCreateConversationId, useChatStore } from "@/lib/hooks/useChatStore";

export default function ChatWidget() {
  const isOpen = useChatStore((state) => state.isOpen);
  const toggleOpen = useChatStore((state) => state.toggleOpen);
  const close = useChatStore((state) => state.close);
  const conversationId = useChatStore((state) => state.conversationId);
  const setConversationId = useChatStore((state) => state.setConversationId);

  useEffect(() => {
    if (!conversationId) {
      setConversationId(getOrCreateConversationId());
    }
  }, [conversationId, setConversationId]);

  return (
    <>
      <ChatModal open={isOpen} onOpenChange={(openState) => !openState && close()} />
      <div id="chat-widget" className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50">
        <button
          type="button"
          onClick={toggleOpen}
          aria-expanded={isOpen}
          aria-label={isOpen ? "Fechar chat" : "Abrir chat"}
          className="flex h-12 w-12 sm:h-14 sm:w-14 items-center justify-center rounded-full bg-slate-900 text-xl sm:text-2xl text-white shadow-2xl hover:bg-slate-800 hover:scale-105 transition-all focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          💬
        </button>
      </div>
    </>
  );
}

