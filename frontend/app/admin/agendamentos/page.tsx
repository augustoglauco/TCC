"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  cancelarAgendamento,
  criarAgendamentoManual,
  fetchAdminAgendamentos,
  fetchGoogleCalendarEvents,
} from "@/lib/api/agendamentos";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type {
  Agendamento,
  AgendamentoManualInput,
  GoogleCalendarEvent,
} from "@/lib/types/agendamentos";
import { AgendamentosSystemTab } from "./AgendamentosSystemTab";
import { GoogleCalendarTab } from "./GoogleCalendarTab";
import { AgendamentoManualModal } from "./AgendamentoManualModal";

const FORM_VAZIO: AgendamentoManualInput = {
  user_email: "",
  nome_cliente: "",
  telefone: "",
  data_hora_inicio: "",
  duracao_minutos: 60,
  descricao: "",
};

export default function AdminAgendamentosPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  const [activeTab, setActiveTab] = useState<"sistema" | "google">("sistema");
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

  const [modalAberto, setModalAberto] = useState(false);
  const [submittingManual, setSubmittingManual] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualForm, setManualForm] = useState<AgendamentoManualInput>(FORM_VAZIO);

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
      setError(err instanceof Error ? err.message : "Erro ao carregar agendamentos.");
    } finally {
      setLoading(false);
    }
  }, []);

  const carregarGoogle = useCallback(async () => {
    try {
      const eventos = await fetchGoogleCalendarEvents();
      setGoogleEvents(eventos);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar eventos do Google.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      if (activeTab === "sistema") {
        void carregarSistema();
      } else {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        void carregarGoogle();
      }
    }
  }, [isAdmin, activeTab, carregarSistema, carregarGoogle]);

  const handleCancelar = async (item: Agendamento) => {
    if (!confirm(`Deseja realmente cancelar a visita de ${item.nome_cliente}?`)) return;
    try {
      await cancelarAgendamento(item.id, item.user_email);
      setAgendamentos((prev) =>
        prev.map((a) => (a.id === item.id ? { ...a, status: "cancelado" } : a)),
      );
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "Erro ao cancelar agendamento.");
    }
  };

  const handleCriarManual = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingManual(true);
    setManualError(null);
    try {
      await criarAgendamentoManual({
        ...manualForm,
        data_hora_inicio: new Date(manualForm.data_hora_inicio).toISOString(),
        duracao_minutos: manualForm.duracao_minutos ? Number(manualForm.duracao_minutos) : 60,
      });
      setModalAberto(false);
      setManualForm(FORM_VAZIO);
      setLoading(true);
      void carregarSistema();
    } catch (err: unknown) {
      setManualError(err instanceof Error ? err.message : "Erro ao criar agendamento manual.");
    } finally {
      setSubmittingManual(false);
    }
  };

  if (!user || !isAdmin) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center space-y-4">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-2xl">
          🚫
        </div>
        <h1 className="text-2xl font-bold text-red-600">Acesso Restrito</h1>
        <p className="text-sm text-slate-600">
          Apenas administradores podem acessar esta página de gestão de agendamentos.
        </p>
        <Link
          href="/"
          className="inline-flex items-center rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Voltar para Início
        </Link>
      </div>
    );
  }

  const totalConfirmados = agendamentos.filter((a) => a.status === "confirmado").length;
  const totalCancelados = agendamentos.filter((a) => a.status === "cancelado").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 space-y-8">
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Painel de Agendamentos
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Gerencie visitas de clientes e visualize eventos sincronizados no Google Calendar.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalAberto(true)}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-purple-500 cursor-pointer transition-colors self-start sm:self-auto"
        >
          <span>➕</span> + Agendar Manualmente
        </button>
      </div>

      {/* Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <span className="text-xs font-semibold uppercase text-slate-500">
            Total de Agendamentos
          </span>
          <p className="mt-2 text-2xl font-bold text-slate-900">{agendamentos.length}</p>
        </div>
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-5 shadow-xs">
          <span className="text-xs font-semibold uppercase text-emerald-700">Confirmados</span>
          <p className="mt-2 text-2xl font-bold text-emerald-800">{totalConfirmados}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-5 shadow-xs">
          <span className="text-xs font-semibold uppercase text-slate-500">Cancelados</span>
          <p className="mt-2 text-2xl font-bold text-slate-700">{totalCancelados}</p>
        </div>
      </div>

      {/* Abas */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-8" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === "sistema"}
            onClick={() => setActiveTab("sistema")}
            className={`py-3 px-1 text-sm font-medium border-b-2 cursor-pointer transition-colors ${
              activeTab === "sistema"
                ? "border-purple-600 text-purple-600 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            }`}
          >
            📋 Agendamentos do Sistema (Por Usuário)
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "google"}
            onClick={() => setActiveTab("google")}
            className={`py-3 px-1 text-sm font-medium border-b-2 cursor-pointer transition-colors ${
              activeTab === "google"
                ? "border-purple-600 text-purple-600 font-semibold"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            }`}
          >
            📅 Google Calendar (Tempo Real)
          </button>
        </nav>
      </div>

      {activeTab === "sistema" && (
        <AgendamentosSystemTab
          agendamentos={agendamentos}
          loading={loading}
          error={error}
          filtroEmail={filtroEmail}
          filtroStatus={filtroStatus}
          onFiltroEmailChange={setFiltroEmail}
          onFiltroStatusChange={setFiltroStatus}
          onFiltrar={() => {
            setLoading(true);
            setError(null);
            void carregarSistema();
          }}
          onCancelar={handleCancelar}
        />
      )}

      {activeTab === "google" && (
        <GoogleCalendarTab
          googleEvents={googleEvents}
          loading={loading}
          error={error}
          onAtualizar={() => {
            setLoading(true);
            setError(null);
            void carregarGoogle();
          }}
        />
      )}

      {modalAberto && (
        <AgendamentoManualModal
          form={manualForm}
          submitting={submittingManual}
          error={manualError}
          onFormChange={setManualForm}
          onSubmit={handleCriarManual}
          onClose={() => setModalAberto(false)}
        />
      )}
    </div>
  );
}
