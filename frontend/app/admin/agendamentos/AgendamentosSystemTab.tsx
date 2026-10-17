"use client";

import type { Agendamento } from "@/lib/types/agendamentos";

function formatarDataHora(dataIso: string): string {
  try {
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(
      new Date(dataIso),
    );
  } catch {
    return dataIso;
  }
}

interface Props {
  agendamentos: Agendamento[];
  loading: boolean;
  error: string | null;
  filtroEmail: string;
  filtroStatus: string;
  onFiltroEmailChange: (v: string) => void;
  onFiltroStatusChange: (v: string) => void;
  onFiltrar: () => void;
  onCancelar: (item: Agendamento) => void;
}

export function AgendamentosSystemTab({
  agendamentos,
  loading,
  error,
  filtroEmail,
  filtroStatus,
  onFiltroEmailChange,
  onFiltroStatusChange,
  onFiltrar,
  onCancelar,
}: Props) {
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <input
          type="text"
          placeholder="Filtrar por e-mail ou nome..."
          value={filtroEmail}
          onChange={(e) => onFiltroEmailChange(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none"
        />
        <select
          value={filtroStatus}
          onChange={(e) => onFiltroStatusChange(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none bg-white"
        >
          <option value="">Todos os status</option>
          <option value="confirmado">Confirmados</option>
          <option value="cancelado">Cancelados</option>
        </select>
        <button
          type="button"
          onClick={onFiltrar}
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
                  <td className="px-4 py-3 text-xs max-w-xs truncate">{item.descricao || "—"}</td>
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
                        onClick={() => onCancelar(item)}
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
  );
}
