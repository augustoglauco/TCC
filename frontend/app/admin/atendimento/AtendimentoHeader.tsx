"use client";

interface AtendimentoHeaderProps {
  atendenteNome: string;
  atendenteId: string;
  errorMessage: string | null;
  onDismissError: () => void;
}

export function AtendimentoHeader({
  atendenteNome,
  atendenteId,
  errorMessage,
  onDismissError,
}: AtendimentoHeaderProps) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5 bg-white rounded-xl border border-slate-200 shadow-2xs shrink-0">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800 font-bold text-lg">
          🎧
        </div>
        <div>
          <h1 className="text-sm font-bold text-slate-900">Central de Atendimento Humano</h1>
          <p className="text-[11px] text-slate-500">
            Fila de transbordo e suporte Human-in-the-Loop em tempo real
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {errorMessage && (
          <div className="px-3 py-1 bg-red-50 border border-red-200 text-red-700 text-xs rounded-md flex items-center gap-1.5">
            <span>⚠️</span>
            <span>{errorMessage}</span>
            <button
              type="button"
              onClick={onDismissError}
              className="ml-1 text-red-500 hover:text-red-800 font-bold"
            >
              ✕
            </button>
          </div>
        )}

        <div className="flex items-center gap-2 text-xs bg-slate-50 border border-slate-200 px-3 py-1.5 rounded-lg text-slate-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-semibold">{atendenteNome}</span>
          <span className="text-[10px] text-slate-400">({atendenteId})</span>
        </div>
      </div>
    </div>
  );
}
