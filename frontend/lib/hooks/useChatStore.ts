import { create } from "zustand";

import type { ChatUIMessage } from "@/lib/types/chat";
import { generateId } from "@/lib/utils/generateId";

export const SESSION_STORAGE_KEY = "tcc_chat_session_conversation_id";
export const USER_STORAGE_PREFIX = "tcc_chat_user_conversation_id_";
export const LEGACY_STORAGE_KEY = "tcc_chat_conversation_id";

export function getUserConversationStorageKey(email: string): string {
  return `${USER_STORAGE_PREFIX}${email.trim().toLowerCase()}`;
}

const temTexto = (valor?: string | null): valor is string => Boolean(valor && valor.trim());

/** Executa um acesso a storage; em navegadores com storage bloqueado (modo
 * privado, quota) devolve o fallback em vez de propagar — único ponto do
 * arquivo que engole a exceção. */
function tentarStorage<T>(acao: () => T, fallback: () => T): T {
  try {
    return acao();
  } catch {
    return fallback();
  }
}

/** Grava o id no storage adequado; `limparSessao` descarta o id da sessão antes. */
function gravarConversationId(id: string, userEmail?: string | null, limparSessao = false): void {
  tentarStorage(
    () => {
      if (limparSessao) window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
      if (temTexto(userEmail)) {
        window.localStorage.setItem(getUserConversationStorageKey(userEmail), id);
      } else {
        window.sessionStorage.setItem(SESSION_STORAGE_KEY, id);
      }
    },
    () => undefined,
  );
}

function idDoUsuario(userEmail: string): string {
  const userKey = getUserConversationStorageKey(userEmail);
  const existente = window.localStorage.getItem(userKey);
  if (existente) {
    return existente;
  }
  // Se havia uma conversa na sessão antes de logar, vincula ao usuário
  const convId = window.sessionStorage.getItem(SESSION_STORAGE_KEY) || generateId();
  window.localStorage.setItem(userKey, convId);
  window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
  return convId;
}

function idDoVisitante(): string {
  const existente = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
  if (existente) {
    return existente;
  }
  const novo = generateId();
  window.sessionStorage.setItem(SESSION_STORAGE_KEY, novo);
  return novo;
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
  tentarStorage(
    () => window.localStorage.removeItem(LEGACY_STORAGE_KEY),
    () => undefined,
  );

  if (temTexto(userEmail)) {
    const idUsuario = tentarStorage(
      () => idDoUsuario(userEmail),
      () => null,
    );
    if (idUsuario) {
      return idUsuario;
    }
  }
  return tentarStorage(idDoVisitante, generateId);
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
    if (typeof window !== "undefined") gravarConversationId(id, userEmail);
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
    if (typeof window !== "undefined") gravarConversationId(newId, userEmail, true);
    set({ conversationId: newId, messages: [], humanAttendanceStatus: null });
  },
}));
