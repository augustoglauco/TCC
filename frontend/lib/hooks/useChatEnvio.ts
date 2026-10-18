"use client";

import { useState } from "react";

import { sendChatMessage } from "@/lib/api/chat";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { paraStatusAtendimento, useChatStore } from "@/lib/hooks/useChatStore";
import type { ChatEscalonamentoData } from "@/lib/types/chat";
import { metricsFromDone } from "@/lib/utils/chatMetrics";
import { generateId } from "@/lib/utils/generateId";

export interface PendingRetry {
  message?: string;
  audioBase64?: string;
  imageBase64?: string;
  imageName?: string;
}

export interface PendingError {
  text: string;
  retry: PendingRetry;
}

export interface PendingImage {
  base64: string;
  name: string;
}

const AUDIO_FALLBACK_TEXT = "(áudio sem fala reconhecível)";
const AUDIO_PENDING_TEXT = "🎤 Transcrevendo áudio...";
const AUDIO_FAILED_TEXT = "🎤 (não foi possível processar o áudio)";
const NO_RESPONSE_TEXT = "(sem resposta do modelo, tente novamente)";

type CallbacksResposta = Pick<
  Parameters<typeof sendChatMessage>[0],
  "onConversationId" | "onEscalonamento" | "onStatus" | "onToken" | "onDone"
>;

interface UseChatEnvioParams {
  conversationId: string;
  pendingImage: PendingImage | null;
  setPendingImage: (image: PendingImage | null) => void;
  setInput: (value: string) => void;
}

/**
 * Envio de mensagens (texto/imagem e áudio) por SSE: estado de envio, erro com
 * dados para retry e escalonamento, mais os callbacks de streaming que os dois
 * fluxos compartilham.
 */
export function useChatEnvio({
  conversationId,
  pendingImage,
  setPendingImage,
  setInput,
}: UseChatEnvioParams) {
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const setConversationId = useChatStore((state) => state.setConversationId);
  const setHumanAttendanceStatus = useChatStore((state) => state.setHumanAttendanceStatus);

  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<PendingError | null>(null);
  const [escalonamento, setEscalonamento] = useState<ChatEscalonamentoData | null>(null);

  /** Callbacks comuns aos fluxos de texto e áudio: a bolha do assistente é
   * criada no primeiro token (ou no placeholder de status) e atualizada depois. */
  function criarCallbacksResposta(): CallbacksResposta {
    const assistantId = generateId();
    let bolhaCriada = false;
    let textoAcumulado = "";

    function garantirBolha(textoInicial: string) {
      if (!bolhaCriada) {
        bolhaCriada = true;
        addMessage({ id: assistantId, role: "assistant", text: textoInicial });
      } else {
        updateMessage(assistantId, { text: textoInicial });
      }
    }

    return {
      onConversationId: (id) => setConversationId(id),
      onEscalonamento: (data) => setEscalonamento(data),
      onStatus: (status) => {
        // Acompanha se a conversa está (ou deixou de estar) sob atendimento
        // humano — liga/desliga o polling de novas mensagens do atendente
        // (ver `useConversaHumanaPolling`). Os dois fluxos não se misturam:
        // enquanto pausada para atendimento humano, o backend nunca consulta o
        // LLM (`app.api.chat.event_stream_humano`), então "carregando_modelo"
        // só ocorre fora desse modo.
        setHumanAttendanceStatus(paraStatusAtendimento(status));
        if (status === "carregando_modelo") {
          garantirBolha("🤖 Aguarde, consultando documentos internos...");
        }
      },
      onToken: (chunk) => {
        textoAcumulado += chunk;
        garantirBolha(textoAcumulado);
      },
      onDone: (data) => {
        // MVP: garante que a bolha nunca fique travada mostrando o
        // placeholder de status (ou vazia) quando a geração produz zero
        // tokens — ex. logo após um cold-start do modelo local.
        garantirBolha(textoAcumulado || NO_RESPONSE_TEXT);
        updateMessage(assistantId, {
          domain: data.domain,
          backendUsed: data.backend_used,
          metrics: metricsFromDone(data),
          card: data.card ?? undefined,
        });
        if (data.card?.tipo === "grafico" && typeof window !== "undefined") {
          window.dispatchEvent(new CustomEvent("refresh_admin_charts"));
        }
      },
    };
  }

  async function submitMessage(text: string, overrideImage?: PendingImage | null) {
    const trimmed = text.trim();
    // `overrideImage` é usado pelo retry para passar a imagem diretamente,
    // sem depender do estado React (que ainda não teria sido atualizado pelo
    // setPendingImage chamado logo antes no handleRetry).
    const imageToSend = overrideImage !== undefined ? overrideImage : pendingImage;
    if (!trimmed && !imageToSend) return;
    if (isSending) return;

    setPendingImage(null);

    const userText = trimmed
      ? imageToSend
        ? `${trimmed} [🖼️ ${imageToSend.name}]`
        : trimmed
      : `[🖼️ ${imageToSend!.name}]`;

    addMessage({ id: generateId(), role: "user", text: userText });
    setInput("");
    setIsSending(true);
    setError(null);

    await sendChatMessage({
      message: trimmed || undefined,
      imageBase64: imageToSend?.base64,
      userEmail: useAuthStore.getState().user?.email,
      authToken: useAuthStore.getState().token,
      conversationId: conversationId || undefined,
      onTranscription: () => {},
      ...criarCallbacksResposta(),
      onError: (msg) => {
        setError({
          text: msg,
          retry: {
            message: trimmed,
            imageBase64: imageToSend?.base64,
            imageName: imageToSend?.name,
          },
        });
      },
    });

    setIsSending(false);
  }

  async function submitAudio(audioBase64: string) {
    if (isSending) return;

    const pendingId = generateId();
    addMessage({ id: pendingId, role: "user", text: AUDIO_PENDING_TEXT });
    setIsSending(true);
    setError(null);

    let transcricaoRecebida = false;

    await sendChatMessage({
      audioBase64,
      userEmail: useAuthStore.getState().user?.email,
      authToken: useAuthStore.getState().token,
      conversationId: conversationId || undefined,
      onTranscription: (text) => {
        transcricaoRecebida = true;
        updateMessage(pendingId, { text: text || AUDIO_FALLBACK_TEXT });
      },
      ...criarCallbacksResposta(),
      onError: (msg) => {
        if (!transcricaoRecebida) {
          updateMessage(pendingId, { text: AUDIO_FAILED_TEXT });
        }
        setError({ text: msg, retry: { audioBase64 } });
      },
    });

    setIsSending(false);
  }

  function handleRetry() {
    if (!error) return;
    const { retry } = error;
    setError(null);
    if (retry.audioBase64) {
      void submitAudio(retry.audioBase64);
    } else {
      // Passa a imagem diretamente para submitMessage em vez de chamar
      // setPendingImage antes — setState é assíncrono e o estado ainda seria
      // null quando submitMessage lesse pendingImage no mesmo ciclo de render.
      const img =
        retry.imageBase64 && retry.imageName
          ? { base64: retry.imageBase64, name: retry.imageName }
          : null;
      void submitMessage(retry.message ?? "", img);
    }
  }

  return {
    isSending,
    error,
    setError,
    escalonamento,
    setEscalonamento,
    submitMessage,
    submitAudio,
    handleRetry,
  };
}
