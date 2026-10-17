"use client";

interface AgendamentosTabsProps {
  activeTab: "sistema" | "google";
  onChange: (tab: "sistema" | "google") => void;
}

export function AgendamentosTabs({ activeTab, onChange }: AgendamentosTabsProps) {
  const tabCls = (tab: "sistema" | "google") =>
    `py-3 px-1 text-sm font-medium border-b-2 cursor-pointer transition-colors ${
      activeTab === tab
        ? "border-purple-600 text-purple-600 font-semibold"
        : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
    }`;

  return (
    <div className="border-b border-slate-200">
      <nav className="flex space-x-8" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === "sistema"}
          onClick={() => onChange("sistema")}
          className={tabCls("sistema")}
        >
          📋 Agendamentos do Sistema (Por Usuário)
        </button>
        <button
          role="tab"
          aria-selected={activeTab === "google"}
          onClick={() => onChange("google")}
          className={tabCls("google")}
        >
          📅 Google Calendar (Tempo Real)
        </button>
      </nav>
    </div>
  );
}
