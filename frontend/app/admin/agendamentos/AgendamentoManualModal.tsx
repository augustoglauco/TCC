"use client";

import type { AgendamentoManualInput } from "@/lib/types/agendamentos";

interface Props {
  form: AgendamentoManualInput;
  submitting: boolean;
  error: string | null;
  onFormChange: (form: AgendamentoManualInput) => void;
  onSubmit: (e: React.FormEvent) => void;
  onClose: () => void;
}

export function AgendamentoManualModal({
  form,
  submitting,
  error,
  onFormChange,
  onSubmit,
  onClose,
}: Props) {
  const set = (patch: Partial<AgendamentoManualInput>) => onFormChange({ ...form, ...patch });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl space-y-4">
        <h3 className="text-lg font-bold text-slate-900">Novo Agendamento Manual</h3>
        <p className="text-xs text-slate-600">
          O agendamento manual checará conflitos no Google Calendar e gravará a visita no sistema.
        </p>

        {error && (
          <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-3">
          <div>
            <label htmlFor="user_email" className="block text-xs font-semibold text-slate-700">
              E-mail do Cliente
            </label>
            <input
              id="user_email"
              type="email"
              required
              value={form.user_email}
              onChange={(e) => set({ user_email: e.target.value })}
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
              value={form.nome_cliente}
              onChange={(e) => set({ nome_cliente: e.target.value })}
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
              value={form.telefone || ""}
              onChange={(e) => set({ telefone: e.target.value })}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label
                htmlFor="data_hora_inicio"
                className="block text-xs font-semibold text-slate-700"
              >
                Data e Hora de Início
              </label>
              <input
                id="data_hora_inicio"
                type="datetime-local"
                required
                value={form.data_hora_inicio}
                onChange={(e) => set({ data_hora_inicio: e.target.value })}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
              />
            </div>

            <div>
              <label
                htmlFor="duracao_minutos"
                className="block text-xs font-semibold text-slate-700"
              >
                Duração (minutos)
              </label>
              <input
                id="duracao_minutos"
                type="number"
                min={15}
                step={15}
                required
                value={form.duracao_minutos ?? 60}
                onChange={(e) =>
                  set({ duracao_minutos: e.target.value === "" ? null : Number(e.target.value) })
                }
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label htmlFor="descricao" className="block text-xs font-semibold text-slate-700">
              Descrição / Motivo da Visita
            </label>
            <textarea
              id="descricao"
              rows={2}
              value={form.descricao || ""}
              onChange={(e) => set({ descricao: e.target.value })}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-3 pt-3">
            <button
              type="button"
              disabled={submitting}
              onClick={onClose}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer disabled:opacity-50"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-500 cursor-pointer disabled:opacity-50"
            >
              {submitting ? "Salvando..." : "Confirmar Agendamento"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
