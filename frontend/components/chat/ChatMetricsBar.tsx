"use client";

interface Props {
  onExportCsv: () => void;
  onExportJson: () => void;
}

export function ChatMetricsBar({ onExportCsv, onExportJson }: Props) {
  return (
    <div className="flex items-center justify-between border-b border-slate-200/80 bg-slate-100/90 backdrop-blur-xs px-3 sm:px-4 py-1.5 text-xs shrink-0 shadow-2xs">
      <span className="text-slate-600 font-semibold flex items-center gap-1.5 text-[11px] sm:text-xs">
        <span className="text-blue-600">📊</span>
        <span className="hidden sm:inline">Métricas de Desempenho &amp; Telemetria</span>
        <span className="sm:hidden">Telemetria</span>
      </span>
      <div className="flex items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          onClick={onExportCsv}
          className="rounded-lg bg-slate-900 px-2.5 py-1 text-[10px] sm:text-[11px] font-semibold text-white hover:bg-slate-800 transition-all active:scale-95 flex items-center gap-1 shadow-2xs cursor-pointer"
        >
          <span>📥</span> <span className="hidden xs:inline">Exportar </span>CSV
        </button>
        <button
          type="button"
          onClick={onExportJson}
          className="rounded-lg bg-slate-200/90 border border-slate-300/60 px-2.5 py-1 text-[10px] sm:text-[11px] font-semibold text-slate-800 hover:bg-slate-300 transition-all active:scale-95 flex items-center gap-1 shadow-2xs cursor-pointer"
        >
          <span>📥</span> <span className="hidden xs:inline">Exportar </span>JSON
        </button>
      </div>
    </div>
  );
}
