"use client";

import { useEffect, useState } from "react";
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

function formatarDataHora(dataIso: string): string {
  try {
    const d = new Date(dataIso);
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(d);
  } catch {
    return dataIso;
  }
}

export default function AdminAgendamentosPage() {
  const user = useAuthStore((state) => state.user);
  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  const [activeTab, setActiveTab] = useState<"sistema" | "google">("sistema");
  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  const [googleEvents, setGoogleEvents] = useState<GoogleCalendarEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filtros Aba 1 (Sistema)
  const [filtroEmail, setFiltroEmail] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");

  // Modal Agendamento Manual
  const [modalAberto, setModalAberto] = useState(false);
  const [submittingManual, setSubmittingManual] = useState(false);
  const [manualError, setManualError] = useState<string | null>(null);
  const [manualForm, setManualForm] = useState<AgendamentoManualInput>({
    user_email: "",
    nome_cliente: "",
    telefone: "",
    data_hora_inicio: "",
    descricao: "",
  });

  const carregarSistema = async () => {
    setLoading(true);
    setError(null);
    try {
      const dados = await fetchAdminAgendamentos({
        filtroEmail: filtroEmail.trim() || undefined,
        status: filtroStatus || undefined,
      });
      setAgendamentos(dados);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao carregar agendamentos.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const carregarGoogle = async () => {
    setLoading(true);
    setError(null);
    try {
      const eventos = await fetchGoogleCalendarEvents();
      setGoogleEvents(eventos);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao carregar eventos do Google.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isAdmin) {
      if (activeTab === "sistema") {
        carregarSistema();
      } else {
        carregarGoogle();
      }
    }
  }, [isAdmin, activeTab]);

  const handleCancelar = async (item: Agendamento) => {
    if (!confirm(`Deseja realmente cancelar a visita de ${item.nome_cliente}?`)) return;
    try {
      await cancelarAgendamento(item.id, item.user_email);
      setAgendamentos((prev) =>
        prev.map((a) => (a.id === item.id ? { ...a, status: "cancelado" } : a))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao cancelar agendamento.";
      alert(msg);
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
      });
      setModalAberto(false);
      setManualForm({
        user_email: "",
        nome_cliente: "",
        telefone: "",
        data_hora_inicio: "",
        descricao: "",
      });
      carregarSistema();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao criar agendamento manual.";
      setManualError(msg);
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
      {/* Header */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-purple-50 px-3 py-1 text-xs font-semibold text-purple-700">
            <span>🛡️</span> Administração de Visitas
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
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

      {/* Cards de Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
          <span className="text-xs font-semibold uppercase text-slate-500">Total de Agendamentos</span>
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

      {/* Navegação por Abas */}
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

      {/* Conteúdo Aba 1: Sistema */}
      {activeTab === "sistema" && (
        <div className="space-y-4">
          {/* Barra de Filtros */}
          <div className="flex flex-col sm:flex-row gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
            <input
              type="text"
              placeholder="Filtrar por e-mail ou nome..."
              value={filtroEmail}
              onChange={(e) => setFiltroEmail(e.target.value)}
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
            />
            <select
              value={filtroStatus}
              onChange={(e) => setFiltroStatus(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none bg-white"
            >
              <option value="">Todos os status</option>
              <option value="confirmado">Confirmados</option>
              <option value="cancelado">Cancelados</option>
            </select>
            <button
              type="button"
              onClick={carregarSistema}
              className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 cursor-pointer"
            >
              Filtrar
            </button>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm">Carregando agendamentos...</div>
          ) : error ? (
            <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-700 text-sm">
              {error}
            </div>
          ) : agendamentos.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-sm rounded-xl border border-slate-200 bg-white">
              Nenhum agendamento encontrado para os filtros selecionados.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-xs">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Cliente</th>
                    <th className="px-4 py-3">Horário</th>
                    <th className="px-4 py-3">Descrição</th>
                    <th className="px-4 py-3">Origem</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3 text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {agendamentos.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/60">
                      <td className="px-4 py-3">
                        <div className="font-semibold text-slate-900">{item.nome_cliente}</div>
                        <div className="text-xs text-slate-500">{item.user_email}</div>
                        {item.telefone && (
                          <div className="text-xs text-slate-400">📞 {item.telefone}</div>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-800">
                        {formatarDataHora(item.data_hora_inicio)}
                      </td>
                      <td className="px-4 py-3 text-xs max-w-xs truncate">
                        {item.descricao || "—"}
                      </td>
                      <td className="px-4 py-3 text-xs">
                        <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-600">
                          {item.origem === "chat" ? "Chat IA" : "Manual"}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex rounded-full px-2 py-0.5 text-xs font-bold ${
                            item.status === "confirmado"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {item.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right space-x-2">
                        {item.google_event_link && (
                          <a
                            href={item.google_event_link}
                            target="_blank"
                            rel="noreferrer"
                            className="text-xs font-semibold text-purple-600 hover:underline inline-block"
                          >
                            Google ↗
                          </a>
                        )}
                        {item.status === "confirmado" && (
                          <button
                            type="button"
                            onClick={() => handleCancelar(item)}
                            className="text-xs font-semibold text-red-600 hover:text-red-800 cursor-pointer"
                          >
                            Desmarcar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Conteúdo Aba 2: Google Calendar */}
      {activeTab === "google" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex items-center justify-between">
            <span className="text-sm text-slate-600">
              Eventos consultados diretamente da agenda corporativa via protocolo MCP.
            </span>
            <button
              type="button"
              onClick={carregarGoogle}
              className="rounded-lg bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-slate-700 cursor-pointer"
            >
              🔄 Atualizar Agenda
            </button>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500 text-sm">Consultando Google Calendar...</div>
          ) : error ? (
            <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-700 text-sm">
              {error}
            </div>
          ) : googleEvents.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-sm rounded-xl border border-slate-200 bg-white">
              Nenhum evento encontrado no período consultado.
            </div>
          ) : (
            <div className="space-y-3">
              {googleEvents.map((evt) => {
                const startTime =
                  evt.start_time ||
                  (typeof evt.start === "string" ? evt.start : evt.start?.dateTime || evt.start?.date) ||
                  "";
                return (
                  <div
                    key={evt.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs"
                  >
                    <div>
                      <h4 className="font-bold text-slate-900">{evt.summary || "(Sem Título)"}</h4>
                      {startTime && (
                        <p className="text-xs text-slate-600 mt-1">🕒 {formatarDataHora(startTime)}</p>
                      )}
                      {evt.description && (
                        <p className="text-xs text-slate-500 mt-1 max-w-xl">{evt.description}</p>
                      )}
                    </div>
                    {evt.html_link && (
                      <a
                        href={evt.html_link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs font-semibold text-purple-600 hover:underline shrink-0"
                      >
                        Ver no Google ↗
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Modal Agendamento Manual */}
      {modalAberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Novo Agendamento Manual</h3>
            <p className="text-xs text-slate-600">
              O agendamento manual checará conflitos no Google Calendar e gravará a visita no sistema.
            </p>

            {manualError && (
              <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs">
                {manualError}
              </div>
            )}

            <form onSubmit={handleCriarManual} className="space-y-3">
              <div>
                <label htmlFor="user_email" className="block text-xs font-semibold text-slate-700">
                  E-mail do Cliente
                </label>
                <input
                  id="user_email"
                  type="email"
                  required
                  value={manualForm.user_email}
                  onChange={(e) => setManualForm({ ...manualForm, user_email: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="nome_cliente" className="block text-xs font-semibold text-slate-700">
                  Nome do Cliente
                </label>
                <input
                  id="nome_cliente"
                  type="text"
                  required
                  value={manualForm.nome_cliente}
                  onChange={(e) => setManualForm({ ...manualForm, nome_cliente: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="telefone" className="block text-xs font-semibold text-slate-700">
                  Telefone
                </label>
                <input
                  id="telefone"
                  type="text"
                  value={manualForm.telefone || ""}
                  onChange={(e) => setManualForm({ ...manualForm, telefone: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="data_hora_inicio" className="block text-xs font-semibold text-slate-700">
                  Data e Hora de Início
                </label>
                <input
                  id="data_hora_inicio"
                  type="datetime-local"
                  required
                  value={manualForm.data_hora_inicio}
                  onChange={(e) => setManualForm({ ...manualForm, data_hora_inicio: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div>
                <label htmlFor="descricao" className="block text-xs font-semibold text-slate-700">
                  Descrição / Motivo da Visita
                </label>
                <textarea
                  id="descricao"
                  rows={2}
                  value={manualForm.descricao || ""}
                  onChange={(e) => setManualForm({ ...manualForm, descricao: e.target.value })}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  disabled={submittingManual}
                  onClick={() => setModalAberto(false)}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submittingManual}
                  className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-500 cursor-pointer disabled:opacity-50"
                >
                  {submittingManual ? "Salvando..." : "Confirmar Agendamento"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
