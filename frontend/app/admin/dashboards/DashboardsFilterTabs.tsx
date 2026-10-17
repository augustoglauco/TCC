"use client";

interface DashboardsFilterTabsProps {
  filterTab: "todos" | "fixados";
  totalCount: number;
  fixadosCount: number;
  displayedCount: number;
  onChange: (tab: "todos" | "fixados") => void;
}

export function DashboardsFilterTabs({
  filterTab,
  totalCount,
  fixadosCount,
  displayedCount,
  onChange,
}: DashboardsFilterTabsProps) {
  return (
    <div className="mb-6 flex items-center justify-between border-b border-slate-200 pb-2">
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onChange("todos")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
            filterTab === "todos"
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          }`}
        >
          Todos ({totalCount})
        </button>
        <button
          type="button"
          onClick={() => onChange("fixados")}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
            filterTab === "fixados"
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          }`}
        >
          📌 Apenas Fixados ({fixadosCount})
        </button>
      </div>
      <span className="text-xs text-slate-400">{displayedCount} gráfico(s) exibido(s)</span>
    </div>
  );
}
