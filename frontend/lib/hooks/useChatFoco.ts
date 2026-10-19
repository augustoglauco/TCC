import { useEffect, useRef } from "react";

import { useChatStore } from "@/lib/hooks/useChatStore";

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

interface UseChatFocoParams {
  open: boolean;
  controlsDisabled: boolean;
  messages: unknown[];
  error: unknown;
  pendingInput: string | null;
  setInput: (value: string) => void;
}

/**
 * Rolagem e foco do chat: scroll até a última mensagem, salto inicial ao
 * abrir, consumo do `pendingInput` do store e devolução do foco à caixa de
 * mensagem. Extraído de `ChatModal` (R3).
 */
export function useChatFoco({
  open,
  controlsDisabled,
  messages,
  error,
  pendingInput,
  setInput,
}: UseChatFocoParams) {
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
        setInput(pendingInput);
        useChatStore.setState({ pendingInput: null });
      }
    }
    // `setInput` é o setter estável de um `useState`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  // Devolve o foco à caixa sempre que os controles reabrem (fim do envio, fim
  // da gravação de áudio, erro de envio) — ver `focarCaixaMensagem`.
  useEffect(() => {
    if (open && !controlsDisabled) {
      inputRef.current?.focus({ preventScroll: true });
    }
  }, [open, controlsDisabled]);

  return { messagesEndRef, inputRef, focarCaixaMensagem, focarCaixaMensagemSePonteiroPreciso };
}
