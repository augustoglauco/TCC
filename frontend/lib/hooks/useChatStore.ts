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

export function getVisitPrompt(
  user?: { nome?: string; email?: string } | null,
  identifiedEmail?: string | null,
): string {
  if (user?.email && user.email.trim()) {
    const nomeStr = user.nome && user.nome.trim() ? `Nome: ${user.nome.trim()}, ` : "";
    return `Quero agendar uma visita técnica. Meus dados cadastrados: ${nomeStr}E-mail: ${user.email.trim()}.`;
  }
  if (identifiedEmail && identifiedEmail.trim()) {
    return `Quero agendar uma visita técnica. Meu e-mail é ${identifiedEmail.trim()}. Por favor, solicite a data, horário e dados adicionais necessários.`;
  }
  return `Quero agendar uma visita técnica. Por favor, solicite meu e-mail, nome e os dados necessários para o agendamento.`;
}

/** Status de atendimento humano (Fase 4) que liga o polling de novas
 * mensagens no `ChatModal` — `null` fora desse fluxo (IA normal). */
export type HumanAttendanceStatus = "aguardando_humano" | "em_atendimento_humano" | null;

/** Normaliza o `status` bruto da conversa (vindo do SSE ou de
 * `fetchConversationSnapshot`) para `HumanAttendanceStatus` — qualquer
 * outro valor (`aberta`, `encerrada`, ...) não liga o polling. */
export function paraStatusAtendimento(status: string): HumanAttendanceStatus {
  return status === "aguardando_humano" || status === "em_atendimento_humano" ? status : null;
}

interface ChatState {
  isOpen: boolean;
  conversationId: string;
  messages: ChatUIMessage[];
  pendingInput: string | null;
  humanAttendanceStatus: HumanAttendanceStatus;
  toggleOpen: () => void;
  open: () => void;
  openWithPrompt: (promptText: string) => void;
  openVisitChat: (
    user?: { nome?: string; email?: string } | null,
    identifiedEmail?: string | null,
  ) => void;
  close: () => void;
  addMessage: (message: ChatUIMessage) => void;
  updateMessage: (id: string, patch: Partial<Omit<ChatUIMessage, "id">>) => void;
  setConversationId: (id: string, userEmail?: string | null) => void;
  /** Reexibe o histórico gravado — só se ainda não houver mensagem na tela. */
  loadHistory: (messages: ChatUIMessage[]) => void;
  /** Substitui as mensagens em tela pelas do servidor (polling do
   * atendimento humano) — ao contrário de `loadHistory`, não checa se já
   * há mensagens: o servidor é a fonte de verdade enquanto o polling roda. */
  replaceMessages: (messages: ChatUIMessage[]) => void;
  setHumanAttendanceStatus: (status: HumanAttendanceStatus) => void;
  /** Limpa as mensagens em tela e gera um novo conversationId. */
  clearChat: (userEmail?: string | null) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  isOpen: false,
  // Inicia vazio para evitar hidratação inconsistente entre SSR e cliente
  conversationId: "",
  messages: [],
  pendingInput: null,
  humanAttendanceStatus: null,
  toggleOpen: () => set((state) => ({ isOpen: !state.isOpen })),
  open: () => set({ isOpen: true }),
  openWithPrompt: (promptText) => set({ isOpen: true, pendingInput: promptText }),
  openVisitChat: (user, identifiedEmail) => {
    const prompt = getVisitPrompt(user, identifiedEmail);
    set({ isOpen: true, pendingInput: prompt });
  },
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
  replaceMessages: (messages) => set({ messages }),
  setHumanAttendanceStatus: (status) => set({ humanAttendanceStatus: status }),
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
    set({ conversationId: newId, messages: [], humanAttendanceStatus: null });
  },
}));
