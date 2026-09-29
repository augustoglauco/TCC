import { beforeEach, describe, expect, it } from "vitest";
import {
  getOrCreateConversationId,
  getUserConversationStorageKey,
  useChatStore,
} from "@/lib/hooks/useChatStore";

describe("useChatStore — persistência condicional", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    useChatStore.setState({
      conversationId: "",
      messages: [],
      isOpen: false,
    });
  });

  it("para visitante deslogado, gera id e salva em sessionStorage, sem persistir em localStorage", () => {
    const id = getOrCreateConversationId();
    expect(id).toBeTruthy();
    expect(window.sessionStorage.getItem("tcc_chat_session_conversation_id")).toBe(id);
    expect(window.localStorage.getItem("tcc_chat_conversation_id")).toBeNull();
  });

  it("remove a chave legada do localStorage se ela existir", () => {
    window.localStorage.setItem("tcc_chat_conversation_id", "legado-123");
    const id = getOrCreateConversationId();
    expect(window.localStorage.getItem("tcc_chat_conversation_id")).toBeNull();
    expect(window.sessionStorage.getItem("tcc_chat_session_conversation_id")).toBe(id);
  });

  it("para usuário autenticado, persiste em localStorage com chave vinculada ao e-mail", () => {
    const email = "cliente@empresa.com";
    const id = getOrCreateConversationId(email);
    expect(id).toBeTruthy();
    const userKey = getUserConversationStorageKey(email);
    expect(window.localStorage.getItem(userKey)).toBe(id);
    expect(window.sessionStorage.getItem("tcc_chat_session_conversation_id")).toBeNull();
  });

  it("ao autenticar, adota a conversa existente de sessionStorage para a chave do usuário", () => {
    window.sessionStorage.setItem("tcc_chat_session_conversation_id", "conv-sessao-1");
    const email = "ana@empresa.com";
    const id = getOrCreateConversationId(email);

    expect(id).toBe("conv-sessao-1");
    const userKey = getUserConversationStorageKey(email);
    expect(window.localStorage.getItem(userKey)).toBe("conv-sessao-1");
    expect(window.sessionStorage.getItem("tcc_chat_session_conversation_id")).toBeNull();
  });

  it("clearChat limpa mensagens e renova o identificador", () => {
    useChatStore.setState({
      conversationId: "conv-velha",
      messages: [{ id: "1", role: "user", text: "oi" }],
    });

    useChatStore.getState().clearChat();

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().conversationId).not.toBe("conv-velha");
    expect(window.sessionStorage.getItem("tcc_chat_session_conversation_id")).toBe(
      useChatStore.getState().conversationId,
    );
  });
});
