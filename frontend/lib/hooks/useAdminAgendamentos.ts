import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelarAgendamento,
  criarAgendamentoManual,
  fetchAdminAgendamentos,
  fetchGoogleCalendarEvents,
} from "@/lib/api/agendamentos";
import type {
  Agendamento,
  AgendamentoManualInput,
  GoogleCalendarEvent,
} from "@/lib/types/agendamentos";

export type AbaAgendamentos = "sistema" | "google";

export const FORM_VAZIO: AgendamentoManualInput = {
  user_email: "",
  nome_cliente: "",
  telefone: "",
  data_hora_inicio: "",
  duracao_minutos: 60,
  descricao: "",
};

function mensagemDeErro(err: unknown, padrao: string): string {
  return err instanceof Error ? err.message : padrao;
}

/** Estado e ações da listagem admin de agendamentos (aba do sistema, aba do Google, cancelar). */
export function useAdminAgendamentos(habilitado: boolean) {
  const [activeTab, setActiveTab] = useState<AbaAgendamentos>("sistema");
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  const [googleEvents, setGoogleEvents] = useState<GoogleCalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filtroEmail, setFiltroEmail] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const filtrosRef = useRef({ email: filtroEmail, status: filtroStatus });
  useEffect(() => {
    filtrosRef.current = { email: filtroEmail, status: filtroStatus };
  }, [filtroEmail, filtroStatus]);

  const carregarSistema = useCallback(async () => {
    const { email, status } = filtrosRef.current;
    try {
      const dados = await fetchAdminAgendamentos({
        filtroEmail: email.trim() || undefined,
        status: status || undefined,
      });
      setAgendamentos(dados);
      setError(null);
    } catch (err: unknown) {
      setError(mensagemDeErro(err, "Erro ao carregar agendamentos."));
    } finally {
      setLoading(false);
    }
  }, []);

  const carregarGoogle = useCallback(async () => {
    try {
      setGoogleEvents(await fetchGoogleCalendarEvents());
      setError(null);
    } catch (err: unknown) {
      setError(mensagemDeErro(err, "Erro ao carregar eventos do Google."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!habilitado) return;
    if (activeTab === "sistema") {
      void carregarSistema();
    } else {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregarGoogle();
    }
  }, [habilitado, activeTab, carregarSistema, carregarGoogle]);

  const recarregarSistema = () => {
    setLoading(true);
    setError(null);
    void carregarSistema();
  };

  const recarregarGoogle = () => {
    setLoading(true);
    setError(null);
    void carregarGoogle();
  };

  const cancelar = async (item: Agendamento) => {
    if (!confirm(`Deseja realmente cancelar a visita de ${item.nome_cliente}?`)) return;
    try {
      await cancelarAgendamento(item.id, item.user_email);
      setAgendamentos((prev) =>
        prev.map((a) => (a.id === item.id ? { ...a, status: "cancelado" } : a)),
      );
    } catch (err: unknown) {
      alert(mensagemDeErro(err, "Erro ao cancelar agendamento."));
    }
  };

  return {
    activeTab,
    setActiveTab,
    agendamentos,
    googleEvents,
    loading,
    error,
    filtroEmail,
    setFiltroEmail,
    filtroStatus,
    setFiltroStatus,
    recarregarSistema,
    recarregarGoogle,
    cancelar,
  };
}

/** Estado do modal de agendamento manual; `onCriado` roda após o POST bem-sucedido. */
export function useAgendamentoManual(onCriado: () => void) {
  const [aberto, setAberto] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState<AgendamentoManualInput>(FORM_VAZIO);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await criarAgendamentoManual({
        ...form,
        data_hora_inicio: new Date(form.data_hora_inicio).toISOString(),
        duracao_minutos: form.duracao_minutos ? Number(form.duracao_minutos) : 60,
      });
      setAberto(false);
      setForm(FORM_VAZIO);
      onCriado();
    } catch (err: unknown) {
      setError(mensagemDeErro(err, "Erro ao criar agendamento manual."));
    } finally {
      setSubmitting(false);
    }
  };

  return {
    aberto,
    abrir: () => setAberto(true),
    fechar: () => setAberto(false),
    form,
    setForm,
    submitting,
    error,
    submit,
  };
}
