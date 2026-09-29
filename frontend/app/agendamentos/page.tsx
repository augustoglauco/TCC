"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { cancelarAgendamento, fetchMeusAgendamentos } from "@/lib/api/agendamentos";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import type { Agendamento } from "@/lib/types/agendamentos";

function formatarDataHora(dataIso: string): string {
  try {
    const d = new Date(dataIso);
    return new Intl.DateTimeFormat("pt-BR", {
      dateStyle: "full",
      timeStyle: "short",
    }).format(d);
  } catch {
    return dataIso;
  }
}

export default function AgendamentosPage() {
  const user = useAuthStore((state) => state.user);
  const openChat = useChatStore((state) => state.open);

  const [agendamentos, setAgendamentos] = useState<Agendamento[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agendamentoParaCancelar, setAgendamentoParaCancelar] = useState<Agendamento | null>(null);
  const [cancelando, setCancelando] = useState(false);

  const carregarAgendamentos = async (email: string) => {
    setLoading(true);
    setError(null);
    try {
      const dados = await fetchMeusAgendamentos(email);
      setAgendamentos(dados);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao carregar agendamentos.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.email) {
      carregarAgendamentos(user.email);
    }
  }, [user?.email]);

  const handleConfirmarCancelamento = async () => {
    if (!agendamentoParaCancelar || !user?.email) return;
    setCancelando(true);
    try {
      const atualizado = await cancelarAgendamento(agendamentoParaCancelar.id, user.email);
      setAgendamentos((prev) =>
        prev.map((item) => (item.id === atualizado.id ? { ...item, status: "cancelado" } : item))
      );
      setAgendamentoParaCancelar(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Erro ao desmarcar agendamento.";
      alert(msg);
    } finally {
      setCancelando(false);
    }
  };

  if (!user) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
        <div className="border-b border-slate-200 pb-6">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
            <span>📅</span> Gestão de Visitas
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Minhas Visitas & Agendamentos
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Consulte seus horários agendados e gerencie suas visitas com facilidade.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-xs space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-50 text-2xl">
            🔒
          </div>
          <h2 className="text-xl font-bold text-slate-900">Login Necessário</h2>
          <p className="mx-auto max-w-md text-sm text-slate-600">
            Para consultar e gerenciar seus agendamentos, faça login na sua conta. Novos agendamentos
            podem ser solicitados a qualquer momento pelo nosso Chat inteligente!
          </p>
          <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/conta/login"
              className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors"
            >
              Entrar na Conta
            </Link>
            <button
              type="button"
              onClick={openChat}
              className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Agendar Visita pelo Chat 💬
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
            <span>📅</span> Integração MCP Google Calendar
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Minhas Visitas & Agendamentos
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Visitas agendadas para <span className="font-semibold text-slate-800">{user.email}</span>.
          </p>
        </div>

        <button
          type="button"
          onClick={openChat}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-emerald-500 transition-colors cursor-pointer self-start sm:self-auto"
        >
          <span>💬</span> Agendar Nova Visita pelo Chat
        </button>
      </div>

      {/* Banner explicativo */}
      <div className="rounded-xl border border-emerald-100 bg-emerald-50/60 p-4 text-sm text-emerald-900 flex items-start gap-3">
        <span className="text-xl">💡</span>
        <p>
          Precisa de um novo horário? O agendamento é realizado automaticamente pelo nosso{" "}
          <strong className="font-semibold">Assistente Virtual no Chat</strong>. Ele consulta os
          horários disponíveis em tempo real na agenda corporativa e confirma na hora!
        </p>
      </div>

      {/* Estados de Carregamento e Erro */}
      {loading && (
        <div className="py-12 text-center text-slate-500">
          <p className="text-sm">Carregando seus agendamentos...</p>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-center justify-between">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => user?.email && carregarAgendamentos(user.email)}
            className="text-xs font-bold underline hover:text-red-800 cursor-pointer"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Lista de Agendamentos */}
      {!loading && !error && agendamentos.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-600 space-y-3">
          <p className="text-base font-semibold text-slate-800">
            Você ainda não possui agendamentos cadastrados.
          </p>
          <p className="text-sm text-slate-500">
            Abra o chat para solicitar uma visita técnica ou comercial no dia e horário de sua preferência.
          </p>
          <button
            type="button"
            onClick={openChat}
            className="mt-2 inline-flex items-center justify-center rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 cursor-pointer"
          >
            Solicitar Agendamento no Chat
          </button>
        </div>
      )}

      {!loading && !error && agendamentos.length > 0 && (
        <div className="space-y-4">
          {agendamentos.map((item) => {
            const isConfirmado = item.status === "confirmado";
            return (
              <div
                key={item.id}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-shadow hover:shadow-sm"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                        isConfirmado
                          ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                          : "bg-slate-100 text-slate-600 border border-slate-200"
                      }`}
                    >
                      {isConfirmado ? "Confirmado" : "Cancelado"}
                    </span>
                    <span className="text-xs text-slate-400">
                      • {item.origem === "chat" ? "Via Chat" : "Manual (Admin)"}
                    </span>
                  </div>

                  <h3 className="text-base font-bold text-slate-900">
                    {item.descricao || "Visita Técnica / Comercial"}
                  </h3>

                  <p className="text-xs sm:text-sm text-slate-600">
                    🕒 <span className="font-medium text-slate-800">{formatarDataHora(item.data_hora_inicio)}</span>
                  </p>

                  {item.google_event_link && (
                    <a
                      href={item.google_event_link}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 hover:underline pt-1"
                    >
                      Abrir no Google Calendar ↗
                    </a>
                  )}
                </div>

                <div className="flex items-center sm:self-center">
                  {isConfirmado && (
                    <button
                      type="button"
                      onClick={() => setAgendamentoParaCancelar(item)}
                      className="inline-flex items-center justify-center rounded-lg border border-red-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 hover:border-red-300 transition-colors cursor-pointer"
                    >
                      Desmarcar
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Diálogo de Confirmação para Desmarcar */}
      {agendamentoParaCancelar && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900">Desmarcar Visita</h3>
            <p className="text-sm text-slate-600">
              Deseja realmente desmarcar esta visita? O horário será liberado na agenda corporativa e o
              evento do Google Calendar será removido.
            </p>
            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                disabled={cancelando}
                onClick={() => setAgendamentoParaCancelar(null)}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer disabled:opacity-50"
              >
                Não, Manter
              </button>
              <button
                type="button"
                disabled={cancelando}
                onClick={handleConfirmarCancelamento}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 cursor-pointer disabled:opacity-50"
              >
                {cancelando ? "Desmarcando..." : "Sim, Desmarcar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
