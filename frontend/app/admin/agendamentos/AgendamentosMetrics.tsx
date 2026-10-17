"use client";

interface AgendamentosMetricsProps {
  total: number;
  confirmados: number;
  cancelados: number;
}

export function AgendamentosMetrics({ total, confirmados, cancelados }: AgendamentosMetricsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
        <span className="text-xs font-semibold uppercase text-slate-500">
          Total de Agendamentos
        </span>
        <p className="mt-2 text-2xl font-bold text-slate-900">{total}</p>
      </div>
      <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-5 shadow-xs">
        <span className="text-xs font-semibold uppercase text-emerald-700">Confirmados</span>
        <p className="mt-2 text-2xl font-bold text-emerald-800">{confirmados}</p>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-5 shadow-xs">
        <span className="text-xs font-semibold uppercase text-slate-500">Cancelados</span>
        <p className="mt-2 text-2xl font-bold text-slate-700">{cancelados}</p>
      </div>
    </div>
  );
}
