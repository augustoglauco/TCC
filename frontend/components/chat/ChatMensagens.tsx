"use client";

import type { RefObject } from "react";

import { ChatErroAlerta } from "@/components/chat/ChatErroAlerta";
import EscalonamentoBanner from "@/components/chat/EscalonamentoBanner";
import MessageBubble from "@/components/chat/MessageBubble";
import type { ChatEscalonamentoData, ChatUIMessage } from "@/lib/types/chat";

/**
 * Mensagem de boas-vindas mostrada com a conversa vazia. Convida a informar o
 * e-mail junto com a pergunta (opcional): com ele o backend identifica o
 * cadastro e as compras do visitante (R10, classificação do usuário).
 */
export const WELCOME_MESSAGE =
  "Olá! 👋 Sou o assistente virtual da empresa. Posso ajudar com produtos e " +
  "orçamentos, suporte técnico, atendimento (nota fiscal, trocas) e agendamento " +
  "de visitas.\n\n" +
  "Se quiser, informe seu e-mail junto com a sua pergunta. Com ele identificamos " +
  "o seu cadastro e o seu histórico de compras, o que facilita o atendimento e o " +
  "nosso relacionamento com você. É opcional: você pode conversar normalmente " +
  "sem informá-lo. Pode escrever ou gravar um áudio.";

interface ChatMensagensProps {
  messages: ChatUIMessage[];
  escalonamento: ChatEscalonamentoData | null;
  erroTexto: string | null;
  messagesEndRef: RefObject<HTMLDivElement | null>;
  onDismissEscalonamento: () => void;
  onRetry: () => void;
}

/** Área rolável do chat: banner de escalonamento, mensagens e erro de envio. */
export function ChatMensagens({
  messages,
  escalonamento,
  erroTexto,
  messagesEndRef,
  onDismissEscalonamento,
  onRetry,
}: ChatMensagensProps) {
  return (
    <div aria-live="polite" className="flex-1 space-y-3 sm:space-y-4 overflow-y-auto p-2.5 sm:p-4">
      <EscalonamentoBanner escalonamento={escalonamento} onDismiss={onDismissEscalonamento} />
      {messages.length === 0 && (
        // Boas-vindas só de interface (R10): não entra no store nem no
        // banco, e some quando chega a primeira mensagem ou o histórico.
        <MessageBubble message={{ id: "boas-vindas", role: "assistant", text: WELCOME_MESSAGE }} />
      )}
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      {erroTexto !== null && <ChatErroAlerta texto={erroTexto} onRetry={onRetry} />}
      <div ref={messagesEndRef} />
    </div>
  );
}
