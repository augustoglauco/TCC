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

export interface SendChatMessageParams {
  /** Texto digitado pelo usuário. Opcional se `audioBase64` for informado. */
  message?: string;
  /** Áudio gravado (base64), alternativa ao texto — ver `AudioRecorder`. */
  audioBase64?: string;
  conversationId?: string;
}

/**
 * Envia uma mensagem (texto e/ou áudio) ao backend e retorna a resposta
 * síncrona.
 *
 * MVP: sem upload de imagem, sem streaming/SSE (ver `docs/FRONTEND.md`
 * §3/§4) — apenas texto e/ou áudio.
 */
export async function sendChatMessage({
  message,
  audioBase64,
  conversationId,
}: SendChatMessageParams): Promise<ChatMessageResponse> {
  const payload: ChatMessageRequest = {
    message,
    conversation_id: conversationId,
    audio: audioBase64 ?? null,
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
