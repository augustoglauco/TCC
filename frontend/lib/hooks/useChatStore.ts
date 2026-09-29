import { create } from "zustand";

import type { ChatUIMessage } from "@/lib/types/chat";
import { generateId } from "@/lib/utils/generateId";

export const SESSION_STORAGE_KEY = "tcc_chat_session_conversation_id";
export const USER_STORAGE_PREFIX = "tcc_chat_user_conversation_id_";
export const LEGACY_STORAGE_KEY = "tcc_chat_conversation_id";

export function getUserConversationStorageKey(email: string): string {
  return `${USER_STORAGE_PREFIX}${email.trim().toLowerCase()}`;
}

/**
 * Lê o `conversation_id` adequado ou gera um novo (R9/R10).
 * - Para visitante não autenticado: armazena estritamente em `sessionStorage`
 *   (a conversa persiste enquanto navega entre páginas na mesma aba/sessão, mas
 *   não fica gravada no navegador para visitas futuras).
 * - Para usuário autenticado: armazena no `localStorage` vinculado ao e-mail.
 *   Se havia uma conversa na sessão antes do login, adota-a para o usuário.
 */
export function getOrCreateConversationId(userEmail?: string | null): string {
  if (typeof window === "undefined") {
    return "";
  }
  // Limpa chave legada se existir
  try {
    window.localStorage.removeItem(LEGACY_STORAGE_KEY);
  } catch {
    // ignora restrição de storage
  }

  if (userEmail && userEmail.trim()) {
    const userKey = getUserConversationStorageKey(userEmail);
    try {
      const existingUserConv = window.localStorage.getItem(userKey);
      if (existingUserConv) {
        return existingUserConv;
      }
      // Se havia uma conversa na sessão antes de logar, vincula ao usuário
      const sessionConv = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
      const convId = sessionConv || generateId();
      window.localStorage.setItem(userKey, convId);
      window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return convId;
    } catch {
      // fallback
    }
  }

  // Visitante não autenticado:
  try {
    const existingSession = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (existingSession) {
      return existingSession;
    }
    const newId = generateId();
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
    return newId;
  } catch {
    return generateId();
  }
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
  setConversationId: (id: string, userEmail?: string | null) => void;
  /** Reexibe o histórico gravado — só se ainda não houver mensagem na tela. */
  loadHistory: (messages: ChatUIMessage[]) => void;
  /** Limpa as mensagens em tela e gera um novo conversationId. */
  clearChat: (userEmail?: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  isOpen: false,
  // Inicia vazio para evitar hidratação inconsistente entre SSR e cliente
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
  setConversationId: (id, userEmail) => {
    if (typeof window !== "undefined") {
      try {
        if (userEmail && userEmail.trim()) {
          window.localStorage.setItem(getUserConversationStorageKey(userEmail), id);
        } else {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, id);
        }
      } catch {
        // ignora
      }
    }
    set({ conversationId: id });
  },
  // Se o visitante já mandou algo antes da resposta do backend chegar, o
  // histórico não é aplicado (não intercala mensagens antigas com a nova).
  loadHistory: (history) =>
    set((state) => (state.messages.length === 0 ? { messages: history } : {})),
  clearChat: (userEmail) => {
    const newId = generateId();
    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
        if (userEmail && userEmail.trim()) {
          window.localStorage.setItem(getUserConversationStorageKey(userEmail), newId);
        } else {
          window.sessionStorage.setItem(SESSION_STORAGE_KEY, newId);
        }
      } catch {
        // ignora
      }
    }
    set({ conversationId: newId, messages: [] });
  },
}));
