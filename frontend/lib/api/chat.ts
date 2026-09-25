import type {
  ChatDoneEventData,
  ChatMessageRequest,
  ChatUIMessage,
  ConversaHistorico,
} from "@/lib/types/chat";
import { metricsFromDone } from "@/lib/utils/chatMetrics";
import { generateId } from "@/lib/utils/generateId";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

const API_BASE_URL = getApiBaseUrl();

export interface SendChatMessageParams {
  /** Texto digitado pelo usuário. Opcional se `audioBase64` ou `imageBase64` for informado. */
  message?: string;
  /** Áudio gravado (base64), alternativa ao texto — ver `AudioRecorder`. */
  audioBase64?: string;
  /** Imagem (base64 PNG/JPG/WEBP) — OCR extrai o texto no backend (R6). */
  imageBase64?: string;
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
 * Envia uma mensagem (texto, áudio e/ou imagem) ao backend e entrega a resposta
 * incrementalmente via os callbacks (SSE) — nunca lança, erros de
 * rede/HTTP/stream viram chamada a `onError`.
 */
export async function sendChatMessage({
  message,
  audioBase64,
  imageBase64,
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
    image: imageBase64 ?? null,
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
  // MVP: se o stream terminar sem `onDone` nem `onError` terem sido
  // chamados (ex.: o backend fecha a conexão sem emitir `done`/`error`), a
  // UI ficaria travada sem nenhum feedback — essa flag garante que sempre
  // sobra um `onError` nesse caso.
  let concluiu = false;

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
              concluiu = true;
              onDone(json as ChatDoneEventData);
              break;
            case "error":
              concluiu = true;
              onError(json.detail ?? "Erro inesperado. Tente novamente.");
              break;
          }
        }
        sepIndex = buffer.indexOf("\n\n");
      }
    }
  } catch {
    onError("Conexão perdida durante o recebimento da resposta. Tente novamente.");
    return;
  }

  if (!concluiu) {
    onError("Resposta incompleta do servidor. Tente novamente.");
  }
}

/**
 * Busca o histórico gravado da conversa (R9) para reexibir ao reabrir o chat.
 * Conversa que ainda não existe no backend (404) devolve `[]`. Qualquer outra
 * falha devolve `null`: o widget abre vazio, como antes, sem mostrar erro.
 */
export async function fetchConversationHistory(
  conversationId: string,
): Promise<ChatUIMessage[] | null> {
  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/api/chat/conversations/${encodeURIComponent(conversationId)}`,
    );
  } catch {
    return null;
  }
  if (response.status === 404) {
    return [];
  }
  if (!response.ok) {
    return null;
  }
  const historico = (await response.json()) as ConversaHistorico;
  return historico.mensagens.map((mensagem) => {
    if (mensagem.papel === "cliente") {
      return { id: generateId(), role: "user", text: mensagem.texto };
    }
    // Com as métricas gravadas, o painel ⚙️ reaparece igual ao da resposta
    // original; sem elas (mensagens anteriores à migração 0012), só o domínio.
    return {
      id: generateId(),
      role: "assistant",
      text: mensagem.texto,
      domain: mensagem.dominio ?? undefined,
      ...(mensagem.metricas && {
        backendUsed: mensagem.metricas.backend_used,
        metrics: metricsFromDone(mensagem.metricas),
      }),
    };
  });
}
