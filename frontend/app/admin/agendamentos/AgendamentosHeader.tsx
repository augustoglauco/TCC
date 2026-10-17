"use client";

interface AgendamentosHeaderProps {
  onAgendar: () => void;
}

export function AgendamentosHeader({ onAgendar }: AgendamentosHeaderProps) {
  return (
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
        onClick={onAgendar}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-purple-500 cursor-pointer transition-colors self-start sm:self-auto"
      >
        <span>➕</span> + Agendar Manualmente
      </button>
    </div>
  );
}
