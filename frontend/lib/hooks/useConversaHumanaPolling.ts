"use client";

import { useEffect } from "react";

import { fetchConversationSnapshot } from "@/lib/api/chat";
import { paraStatusAtendimento, useChatStore } from "@/lib/hooks/useChatStore";

/**
 * Entrega da mensagem do atendente humano (Fase 4, achado de 2026-10-06):
 * quando um atendente responde pelo painel admin, a mensagem é gravada
 * direto no banco — não existe WebSocket nem SSE do servidor para esse
 * evento chegar ao widget do cliente enquanto ele já está com o chat
 * aberto. Sem isso, "atendente responde mas a mensagem não aparece no
 * chat do cliente" (só reapareceria se o cliente recarregasse a página).
 * Com o widget aberto, repolla o histórico periodicamente e substitui as
 * mensagens em tela pelas do servidor quando a conversa está sob
 * atendimento humano. Também é assim que detectamos quando o atendente
 * encerra/devolve a conversa para a IA (o status deixa de ser humano).
 *
 * Achado de 2026-10-07: gatear o início do polling em
 * `humanAttendanceStatus` já verdadeiro quebrava o caso mais comum —
 * `humanAttendanceStatus` só vira verdadeiro via evento SSE `status` (que
 * só chega numa resposta a uma mensagem DO CLIENTE) ou na checagem única
 * ao montar o `ChatWidget`. Se o atendente assume a conversa enquanto o
 * cliente já está com o chat aberto e parado (sem mandar nada), nada
 * nunca ligava o polling — a mensagem só "chegava" se o cliente mandasse
 * outra mensagem primeiro (o que então disparava o `status` e, por
 * tabela, o polling). Agora o polling roda sempre que o widget está
 * aberto, não só quando já sabemos que está em atendimento humano — é
 * o próprio polling que detecta a entrada nesse modo. MVP: sem
 * WebSocket/SSE do servidor, isso significa uma requisição leve a cada
 * 4s por widget aberto, mesmo em conversas que nunca escalam.
 */
export function useConversaHumanaPolling(open: boolean, conversationId: string) {
  const replaceMessages = useChatStore((state) => state.replaceMessages);
  const setHumanAttendanceStatus = useChatStore((state) => state.setHumanAttendanceStatus);

  useEffect(() => {
    if (!open || !conversationId) {
      return;
    }
    const intervalo = setInterval(async () => {
      const snapshot = await fetchConversationSnapshot(conversationId);
      if (!snapshot) {
        return;
      }
      const statusAnterior = useChatStore.getState().humanAttendanceStatus;
      const novoStatus = paraStatusAtendimento(snapshot.status);
      setHumanAttendanceStatus(novoStatus);
      // Só substitui (e, por tabela, dispara o scroll-to-bottom do efeito
      // do ChatModal, que depende de `messages`) quando o servidor tem
      // conteúdo novo de fato — sem este guard, cada tick de 4s trocava
      // `messages` por uma lista nova idêntica e prendia a tela sempre no
      // fundo, impedindo o cliente de rolar para cima durante a espera.
      //
      // `novoStatus || statusAnterior` (não só `novoStatus`): achado de
      // 2026-10-07 — `devolver_para_ia`/`finalizar_atendimento` gravam uma
      // mensagem de despedida ("Redirecionado para atendente virtual"/"O
      // Atendente encerrou o atendimento.") no mesmo instante em que o
      // status deixa de ser humano. Guardar só por `novoStatus` perdia essa
      // última mensagem: no tick em que a transição é detectada, `novoStatus`
      // já veio `null`, então o `if` nunca chegava a rodar. Com
      // `statusAnterior` também valendo, esse tick de transição ainda
      // processa o replace; os ticks seguintes (os dois `null`) voltam a
      // ficar fora do caminho de uma conversa normal de IA.
      if (
        (novoStatus || statusAnterior) &&
        snapshot.messages.length !== useChatStore.getState().messages.length
      ) {
        replaceMessages(snapshot.messages);
      }
    }, 4000);
    return () => clearInterval(intervalo);
  }, [open, conversationId, replaceMessages, setHumanAttendanceStatus]);
}
