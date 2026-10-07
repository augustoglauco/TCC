"use client";

import { useEffect } from "react";

import { ChatModal } from "@/components/chat/ChatModal";
import { fetchConversationSnapshot } from "@/lib/api/chat";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  getOrCreateConversationId,
  paraStatusAtendimento,
  useChatStore,
} from "@/lib/hooks/useChatStore";

export default function ChatWidget() {
  const isOpen = useChatStore((state) => state.isOpen);
  const toggleOpen = useChatStore((state) => state.toggleOpen);
  const close = useChatStore((state) => state.close);
  const conversationId = useChatStore((state) => state.conversationId);
  const setConversationId = useChatStore((state) => state.setConversationId);
  const loadHistory = useChatStore((state) => state.loadHistory);
  const setHumanAttendanceStatus = useChatStore((state) => state.setHumanAttendanceStatus);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    if (!conversationId) {
      setConversationId(getOrCreateConversationId(user?.email), user?.email);
    }
  }, [conversationId, setConversationId, user?.email]);

  // Retomada (R9): ao ter o id, busca uma vez as mensagens gravadas no
  // backend. Falha ou conversa nova: o chat abre vazio, como antes. Também
  // captura o status (achado de 2026-10-06): se o cliente recarrega a
  // página já com um atendente assumido, o `ChatModal` precisa saber disso
  // de cara para começar o polling de novas mensagens — sem isso, só
  // descobria o status ao enviar a próxima mensagem.
  useEffect(() => {
    if (!conversationId) {
      return;
    }
    let cancelado = false;
    fetchConversationSnapshot(conversationId).then((snapshot) => {
      if (cancelado || !snapshot) {
        return;
      }
      if (snapshot.messages.length > 0) {
        loadHistory(snapshot.messages);
      }
      setHumanAttendanceStatus(paraStatusAtendimento(snapshot.status));
    });
    return () => {
      cancelado = true;
    };
  }, [conversationId, loadHistory, setHumanAttendanceStatus]);

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
