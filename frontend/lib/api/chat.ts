import type { ChatMessageRequest, ChatMessageResponse } from "@/lib/types/chat";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Erro de comunicação com `POST /api/chat/messages` (rede ou HTTP não-2xx). */
export class ChatApiError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ChatApiError";
    this.status = status;
  }
}

/**
 * Envia uma mensagem de texto ao backend e retorna a resposta síncrona.
 *
 * MVP: apenas texto — sem upload de imagem/áudio, sem streaming/SSE (ver
 * `docs/FRONTEND.md` §3/§4); o campo `audio` é sempre `null`.
 */
export async function sendChatMessage(
  message: string,
  conversationId?: string,
): Promise<ChatMessageResponse> {
  const payload: ChatMessageRequest = {
    message,
    conversation_id: conversationId,
    audio: null,
  };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ChatApiError("Não foi possível conectar ao servidor. Verifique sua conexão.");
  }

  if (!response.ok) {
    const message =
      response.status === 503
        ? "Serviço temporariamente indisponível. Tente novamente."
        : "Não foi possível enviar sua mensagem. Tente novamente.";
    throw new ChatApiError(message, response.status);
  }

  return (await response.json()) as ChatMessageResponse;
}
