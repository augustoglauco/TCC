"use client";

import { closeConversation, deleteConversation } from "@/lib/api/chat";
import { solicitarTransbordo } from "@/lib/api/adminAtendimento";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { generateId } from "@/lib/utils/generateId";

interface UseChatAcoesParams {
  conversationId: string;
  onOpenChange: (open: boolean) => void;
  onHistoricoApagado: () => void;
}

function confirmar(mensagem: string): boolean {
  return typeof window === "undefined" || window.confirm(mensagem);
}

/** Ações secundárias da conversa: apagar histórico, encerrar e chamar atendente. */
export function useChatAcoes({
  conversationId,
  onOpenChange,
  onHistoricoApagado,
}: UseChatAcoesParams) {
  const addMessage = useChatStore((state) => state.addMessage);
  const setConversationId = useChatStore((state) => state.setConversationId);
  const clearChat = useChatStore((state) => state.clearChat);

  async function handleClearHistory() {
    if (!confirmar("Deseja apagar todo o histórico e a memória desta conversa no servidor?")) {
      return;
    }
    const ok = await deleteConversation(conversationId);
    if (!ok) {
      window.alert("Não foi possível apagar o histórico agora. Tente novamente em instantes.");
      return;
    }
    const userEmail = useAuthStore.getState().user?.email;
    clearChat(userEmail);
    onHistoricoApagado();
  }

  async function handleCloseConversation() {
    if (!confirmar("Deseja finalizar este atendimento? A sessão será registrada como encerrada.")) {
      return;
    }
    const ok = await closeConversation(conversationId, "manual_usuario");
    if (!ok) {
      // Achado da revisão de 2026-10-04: sem checar o retorno, a UI
      // sempre mostrava "atendimento encerrado" e trocava o conversationId
      // local mesmo quando o POST de encerramento falhava no servidor — a
      // conversa antiga ficava órfã (nunca marcada como encerrada) e o
      // reload resgatava o id antigo do localStorage como se nada tivesse
      // acontecido.
      window.alert("Não foi possível encerrar o atendimento agora. Tente novamente em instantes.");
      return;
    }
    addMessage({
      id: generateId(),
      role: "assistant",
      text: "🏁 Atendimento encerrado. Obrigado pelo contato!",
    });
    const userEmail = useAuthStore.getState().user?.email;
    setConversationId(generateId(), userEmail);
    onOpenChange(false);
  }

  async function handleSolicitarAtendente() {
    if (!confirmar("Deseja falar com um atendente humano? A IA será pausada nesta conversa.")) {
      return;
    }
    try {
      await solicitarTransbordo(conversationId, "solicitacao_cliente");
      addMessage({
        id: generateId(),
        role: "assistant",
        text: "⏳ Solicitação de atendimento humano enviada! Um atendente assumirá este chat em breve. Enquanto isso, o assistente automático está pausado.",
      });
    } catch {
      window.alert("Não foi possível solicitar atendimento humano no momento. Tente novamente.");
    }
  }

  return { handleClearHistory, handleCloseConversation, handleSolicitarAtendente };
}
