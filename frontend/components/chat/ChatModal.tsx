"use client";

import { useEffect, useRef, useState } from "react";

import { ChatDragOverlay } from "@/components/chat/ChatDragOverlay";
import { ChatInputArea } from "@/components/chat/ChatInputArea";
import { ChatMetricsBar } from "@/components/chat/ChatMetricsBar";
import EscalonamentoBanner from "@/components/chat/EscalonamentoBanner";
import MessageBubble from "@/components/chat/MessageBubble";
import { Modal } from "@/components/ui/Modal";
import { useChatAcoes } from "@/lib/hooks/useChatAcoes";
import { useChatDropZone } from "@/lib/hooks/useChatDropZone";
import { type PendingImage, useChatEnvio } from "@/lib/hooks/useChatEnvio";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useConversaHumanaPolling } from "@/lib/hooks/useConversaHumanaPolling";
import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";

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

/**
 * `true` em dispositivos com ponteiro preciso (mouse/trackpad). Em touch,
 * tomar o foco sem o usuário pedir abre o teclado virtual, que come metade da
 * viewport e esconde justamente a última mensagem — por isso a abertura do
 * chat e as ações secundárias só focam a caixa quando isto é verdadeiro
 * (prática dos chats de mercado, discutido em 2026-10-14; ver
 * `docs/FRONTEND.md` §3). Capability query, não user-agent. Sem suporte a
 * `matchMedia` assume desktop, que é o comportamento mais acessível.
 */
function temPonteiroPreciso(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return true;
  }
  return window.matchMedia("(pointer: fine)").matches;
}

export interface ChatModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChatModal({ open, onOpenChange }: ChatModalProps) {
  const messages = useChatStore((state) => state.messages);
  const conversationId = useChatStore((state) => state.conversationId);
  const pendingInput = useChatStore((state) => state.pendingInput);

  const [input, setInput] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [pendingImage, setPendingImage] = useState<PendingImage | null>(null);

  const {
    isSending,
    error,
    setError,
    escalonamento,
    setEscalonamento,
    submitMessage,
    submitAudio,
    handleRetry,
  } = useChatEnvio({ conversationId, pendingImage, setPendingImage, setInput });

  const { handleClearHistory, handleCloseConversation, handleSolicitarAtendente } = useChatAcoes({
    conversationId,
    onOpenChange,
    onHistoricoApagado: () => {
      setError(null);
      setEscalonamento(null);
    },
  });

  const controlsDisabled = isSending || isRecording;
  const canSend = !controlsDisabled && (!!input.trim() || !!pendingImage);

  const { isDraggingOver, handleDragOver, handleDragLeave, handleDrop } = useChatDropZone({
    disabled: controlsDisabled,
    onImage: (base64, name) => setPendingImage({ base64, name }),
    onAudio: (base64) => void submitAudio(base64),
    onError: (text) => setError({ text, retry: {} }),
  });

  useConversaHumanaPolling(open, conversationId);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  /** Devolve o foco à caixa quando o usuário estava compondo e uma ação tirou
   * o foco dele — clicar num botão move o foco para o botão, e o `<input>`
   * ainda fica `disabled` enquanto `controlsDisabled` está ligado. Vale em
   * qualquer dispositivo: o teclado virtual já está aberto nesse momento. O
   * `requestAnimationFrame` espera o re-render que a ação disparou (focar
   * antes dele não tem efeito) e o `preventScroll` evita que o foco puxe o
   * layout e desfaça o scroll da conversa. Para o envio em si, quem devolve o
   * foco é o efeito que observa `controlsDisabled`, porque aí o `<input>` só
   * reabre depois da resposta. */
  function focarCaixaMensagem() {
    const focar = () => inputRef.current?.focus({ preventScroll: true });
    if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") {
      focar();
      return;
    }
    window.requestAnimationFrame(focar);
  }

  /** Igual ao anterior, mas só em ponteiro preciso — ver `temPonteiroPreciso`.
   * Usado nas ações secundárias (exportar, limpar histórico, atendente…), que
   * não são continuação de uma digitação: em touch, trazer o cursor de volta
   * abriria o teclado sem o usuário pedir. */
  function focarCaixaMensagemSePonteiroPreciso() {
    if (!temPonteiroPreciso()) {
      return;
    }
    focarCaixaMensagem();
  }

  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView?.({ behavior: "smooth" });
      if (pendingInput) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setInput(pendingInput);
        useChatStore.setState({ pendingInput: null });
      }
    }
  }, [messages, error, open, pendingInput]);

  // Ao abrir o chat, salta direto para a última mensagem (pedido do usuário,
  // 2026-10-14). O scroll suave do efeito acima não resolve na abertura: ele
  // roda no mesmo commit em que o modal monta, quando a lista ainda não tem
  // altura, e a animação é descartada — a conversa abria no topo. O
  // `requestAnimationFrame` duplo garante o salto depois do primeiro paint,
  // com a lista já medida.
  useEffect(() => {
    if (!open) {
      return;
    }
    let frameInterno = 0;
    const frameExterno = requestAnimationFrame(() => {
      frameInterno = requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView?.({ behavior: "auto", block: "end" });
        if (temPonteiroPreciso()) {
          inputRef.current?.focus({ preventScroll: true });
        }
      });
    });
    return () => {
      cancelAnimationFrame(frameExterno);
      cancelAnimationFrame(frameInterno);
    };
  }, [open]);

  const hasAssistantMessages = messages.some((m) => m.role === "assistant");

  // Devolve o foco à caixa sempre que os controles reabrem (fim do envio, fim
  // da gravação de áudio, erro de envio) — ver `focarCaixaMensagem`.
  useEffect(() => {
    if (open && !controlsDisabled) {
      inputRef.current?.focus({ preventScroll: true });
    }
  }, [open, controlsDisabled]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={
        <div className="flex items-center gap-2 text-slate-900">
          <span className="relative flex h-2.5 w-2.5 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <span className="font-extrabold text-sm sm:text-base tracking-tight">
            Chat com Agente Virtual
          </span>
          <span className="hidden sm:inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] sm:text-[11px] font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
            Ollama + Dual MCP
          </span>
        </div>
      }
      description="Assistente IA multimodal com métricas de inferência em tempo real"
      size="2xl"
    >
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className="relative flex h-[62vh] sm:h-[68vh] min-h-[380px] max-h-[600px] flex-col rounded-xl border border-slate-200 bg-slate-50/50"
      >
        <ChatDragOverlay visible={isDraggingOver} />
        {hasAssistantMessages && (
          <ChatMetricsBar
            onExportCsv={() => {
              exportMetricsToCsv(messages);
              focarCaixaMensagemSePonteiroPreciso();
            }}
            onExportJson={() => {
              exportMetricsToJson(messages);
              focarCaixaMensagemSePonteiroPreciso();
            }}
          />
        )}

        <div
          aria-live="polite"
          className="flex-1 space-y-3 sm:space-y-4 overflow-y-auto p-2.5 sm:p-4"
        >
          <EscalonamentoBanner
            escalonamento={escalonamento}
            onDismiss={() => {
              setEscalonamento(null);
              focarCaixaMensagemSePonteiroPreciso();
            }}
          />
          {messages.length === 0 && (
            // Boas-vindas só de interface (R10): não entra no store nem no
            // banco, e some quando chega a primeira mensagem ou o histórico.
            <MessageBubble
              message={{ id: "boas-vindas", role: "assistant", text: WELCOME_MESSAGE }}
            />
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {error && (
            <div
              role="alert"
              data-testid="chat-error"
              className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 shadow-2xs"
            >
              <p className="font-semibold">{error.text}</p>
              <button
                type="button"
                onClick={() => {
                  handleRetry();
                  focarCaixaMensagemSePonteiroPreciso();
                }}
                className="mt-1 font-bold underline hover:no-underline"
              >
                Tentar novamente
              </button>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <ChatInputArea
          input={input}
          pendingImage={pendingImage}
          controlsDisabled={controlsDisabled}
          isSending={isSending}
          canSend={canSend}
          showActions={messages.length > 0}
          onInputChange={setInput}
          onRemovePendingImage={() => {
            setPendingImage(null);
            focarCaixaMensagem();
          }}
          onSubmit={(e) => {
            e.preventDefault();
            void submitMessage(input);
          }}
          onImageSelected={(base64, name) => {
            setPendingImage({ base64, name });
            focarCaixaMensagem();
          }}
          onRecordingComplete={(audioBase64) => void submitAudio(audioBase64)}
          onRecordingStateChange={setIsRecording}
          onSolicitarAtendente={() => {
            void handleSolicitarAtendente();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          onEncerrar={() => {
            void handleCloseConversation();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          onLimparHistorico={() => {
            void handleClearHistory();
            focarCaixaMensagemSePonteiroPreciso();
          }}
          inputRef={inputRef}
        />
      </div>
    </Modal>
  );
}
