import { create } from "zustand";

import type { ChatUIMessage } from "@/lib/types/chat";
import { generateId } from "@/lib/utils/generateId";

const CONVERSATION_ID_STORAGE_KEY = "tcc_chat_conversation_id";

/**
 * Lê o `conversation_id` do `localStorage` ou gera um novo (R9).
 *
 * MVP: o id fica no navegador (localStorage); as mensagens ficam no
 * backend (Postgres, R9) e o `ChatWidget` as recarrega ao montar, via
 * `GET /api/chat/conversations/{id}` (ver docs/FRONTEND.md §4).
 */
export function getOrCreateConversationId(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const existing = window.localStorage.getItem(CONVERSATION_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const newId = generateId();
  window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, newId);
  return newId;
}

interface ChatState {
  isOpen: boolean;
  conversationId: string;
  messages: ChatUIMessage[];
  toggleOpen: () => void;
  open: () => void;
  close: () => void;
  addMessage: (message: ChatUIMessage) => void;
  updateMessage: (id: string, patch: Partial<Omit<ChatUIMessage, "id">>) => void;
  setConversationId: (id: string) => void;
  /** Reexibe o histórico gravado — só se ainda não houver mensagem na tela. */
  loadHistory: (messages: ChatUIMessage[]) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  isOpen: false,
  // MVP: inicia vazio para não divergir entre render do servidor e do
  // cliente (SSR); o valor real é lido do localStorage em um `useEffect` no
  // `ChatWidget`, no primeiro render do cliente.
  conversationId: "",
  messages: [],
  toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === id ? { ...message, ...patch } : message,
      ),
    })),
  setConversationId: (id) => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(CONVERSATION_ID_STORAGE_KEY, id);
    }
    set({ conversationId: id });
  },
  // Se o visitante já mandou algo antes da resposta do backend chegar, o
  // histórico não é aplicado (não intercala mensagens antigas com a nova).
  loadHistory: (history) =>
    set((state) => (state.messages.length === 0 ? { messages: history } : {})),
}));
