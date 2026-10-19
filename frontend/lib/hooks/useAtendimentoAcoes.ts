import { useState } from "react";
import {
  claimConversa,
  enviarMensagemAtendente,
  fecharAtendimento,
} from "@/lib/api/adminAtendimento";

interface Params {
  token: string | null;
  activeChatId: string | null;
  atendenteId: string;
  atendenteNome: string;
  setActiveChatId: (id: string | null) => void;
  limparChatAtivo: () => void;
  carregarFilaEMeusChats: () => Promise<void>;
  carregarDetalhes: () => Promise<void>;
}

function mensagemDe(err: unknown, padrao: string): string {
  return err instanceof Error ? err.message : padrao;
}

/** Acoes do atendente (assumir, enviar, finalizar, devolver para a IA) e seus estados de carregamento. */
export function useAtendimentoAcoes({
  token,
  activeChatId,
  atendenteId,
  atendenteNome,
  setActiveChatId,
  limparChatAtivo,
  carregarFilaEMeusChats,
  carregarDetalhes,
}: Params) {
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [closing, setClosing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleClaim = async (conversationId: string) => {
    if (!token) return;
    setClaimingId(conversationId);
    setErrorMessage(null);
    try {
      await claimConversa(conversationId, atendenteId, atendenteNome, token);
      setActiveChatId(conversationId);
    } catch (err: unknown) {
      setErrorMessage(mensagemDe(err, "Erro ao assumir atendimento."));
    } finally {
      // Recarrega tanto no sucesso quanto na falha (outro atendente pode ter assumido).
      await carregarFilaEMeusChats();
      setClaimingId(null);
    }
  };

  const handleSendMessage = async (texto: string) => {
    if (!activeChatId || !token) return;
    setSendingMessage(true);
    try {
      await enviarMensagemAtendente(activeChatId, atendenteNome, texto, token);
      await carregarDetalhes();
    } catch (err: unknown) {
      setErrorMessage(mensagemDe(err, "Erro ao enviar mensagem."));
    } finally {
      setSendingMessage(false);
    }
  };

  const encerrar = async (
    acao: "finalizar" | "devolver_ia",
    motivo: string | undefined,
    erroPadrao: string,
  ) => {
    if (!activeChatId || !token) return;
    setClosing(true);
    try {
      await fecharAtendimento(activeChatId, acao, motivo, token);
      limparChatAtivo();
      await carregarFilaEMeusChats();
    } catch (err: unknown) {
      setErrorMessage(mensagemDe(err, erroPadrao));
    } finally {
      setClosing(false);
    }
  };

  const handleFinalizar = (motivo?: string) =>
    encerrar("finalizar", motivo, "Erro ao encerrar atendimento.");

  const handleDevolverIA = () => encerrar("devolver_ia", undefined, "Erro ao devolver para IA.");

  return {
    claimingId,
    sendingMessage,
    closing,
    errorMessage,
    setErrorMessage,
    handleClaim,
    handleSendMessage,
    handleFinalizar,
    handleDevolverIA,
  };
}
