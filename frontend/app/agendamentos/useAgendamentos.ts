"use client";

import { useEffect, useState } from "react";
import { cancelarAgendamento, fetchMeusAgendamentos } from "@/lib/api/agendamentos";
import type { Agendamento } from "@/lib/types/agendamentos";

function mensagemDeErro(err: unknown, padrao: string): string {
  return err instanceof Error ? err.message : padrao;
}

export function useAgendamentos(email: string | undefined) {
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  // Comeca `true`: o efeito carrega assim que `email` existe.
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [agendamentoParaCancelar, setAgendamentoParaCancelar] = useState<Agendamento | null>(null);
  const [cancelando, setCancelando] = useState(false);

  // Nao toca estado antes do primeiro `await`: este loader roda a partir de um
  // efeito, onde setState sincrono dispara render em cascata
  // (react-hooks/set-state-in-effect). Os caminhos interativos ligam o spinner
  // no proprio handler.
  const carregarAgendamentos = async (emailUsuario: string) => {
    try {
      const dados = await fetchMeusAgendamentos(emailUsuario);
      setAgendamentos(dados);
      setError(null);
    } catch (err: unknown) {
      setError(mensagemDeErro(err, "Erro ao carregar agendamentos."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (email) {
      // Falso positivo: `carregarAgendamentos` so toca estado depois de `await fetchMeusAgendamentos`
      // (funcao `async` importada), logo nao ha setState sincrono aqui. A regra
      // nao resolve a assincronia da chamada e assume o pior caso.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregarAgendamentos(email);
    }
  }, [email]);

  const confirmarCancelamento = async () => {
    if (!agendamentoParaCancelar || !email) return;
    setCancelando(true);
    try {
      const atualizado = await cancelarAgendamento(agendamentoParaCancelar.id, email);
      setAgendamentos((prev) =>
        prev.map((item) => (item.id === atualizado.id ? { ...item, status: "cancelado" } : item)),
      );
      setAgendamentoParaCancelar(null);
    } catch (err: unknown) {
      alert(mensagemDeErro(err, "Erro ao desmarcar agendamento."));
    } finally {
      setCancelando(false);
    }
  };

  const recarregar = () => {
    if (!email) return;
    setLoading(true);
    setError(null);
    void carregarAgendamentos(email);
  };

  return {
    agendamentos,
    loading,
    error,
    agendamentoParaCancelar,
    setAgendamentoParaCancelar,
    cancelando,
    confirmarCancelamento,
    recarregar,
  };
}
