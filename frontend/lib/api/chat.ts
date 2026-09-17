import type { ChatDoneEventData, ChatMessageRequest } from "@/lib/types/chat";

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
  onConversationId: (id: string) => void;
  onTranscription: (text: string) => void;
  onStatus: (status: string) => void;
  onToken: (text: string) => void;
  onDone: (data: ChatDoneEventData) => void;
  onError: (message: string) => void;
}

/** Extrai `{ event, data }` de um bloco SSE (linhas `event:`/`data:` até uma linha em branco). */
function parseSseBlock(block: string): { event: string; data: string } | null {
  let event = "message";
  let data = "";
  for (const linha of block.split("\n")) {
    if (linha.startsWith("event:")) {
      event = linha.slice("event:".length).trim();
    } else if (linha.startsWith("data:")) {
      data += linha.slice("data:".length).trim();
    }
  }
  return data ? { event, data } : null;
}

/**
 * Envia uma mensagem (texto e/ou áudio) ao backend e entrega a resposta
 * incrementalmente via os callbacks (SSE) — nunca lança, erros de
 * rede/HTTP/stream viram chamada a `onError`.
 *
 * MVP: sem upload de imagem (ver `docs/FRONTEND.md` §3/§4) — apenas texto
 * e/ou áudio.
 */
export async function sendChatMessage({
  message,
  audioBase64,
  conversationId,
  onConversationId,
  onTranscription,
  onStatus,
  onToken,
  onDone,
  onError,
}: SendChatMessageParams): Promise<void> {
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
    onError("Não foi possível conectar ao servidor. Verifique sua conexão.");
    return;
  }

  if (!response.ok || !response.body) {
    onError(
      response.status === 503
        ? "Serviço temporariamente indisponível. Tente novamente."
        : "Não foi possível enviar sua mensagem. Tente novamente.",
    );
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let sepIndex = buffer.indexOf("\n\n");
      while (sepIndex !== -1) {
        const block = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        const parsed = parseSseBlock(block);
        if (parsed) {
          const json = JSON.parse(parsed.data);
          switch (parsed.event) {
            case "conversation":
              onConversationId(json.conversation_id);
              break;
            case "transcription":
              onTranscription(json.transcribed_message);
              break;
            case "status":
              onStatus(json.status);
              break;
            case "token":
              onToken(json.text);
              break;
            case "done":
              onDone(json as ChatDoneEventData);
              break;
            case "error":
              onError(json.detail ?? "Erro inesperado. Tente novamente.");
              break;
          }
        }
        sepIndex = buffer.indexOf("\n\n");
      }
    }
  } catch {
    onError("Conexão perdida durante o recebimento da resposta. Tente novamente.");
  }
}
