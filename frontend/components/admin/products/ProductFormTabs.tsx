"use client";

import React from "react";

export type ActiveTab = "geral" | "estoque" | "descontos" | "compatibilidades";

interface ProductFormTabsProps {
  activeTab: ActiveTab;
  estoqueTotal: number;
  descontosCount: number;
  compatibilidadesCount: number;
  onChange: (tab: ActiveTab) => void;
}

export function ProductFormTabs({
  activeTab,
  estoqueTotal,
  descontosCount,
  compatibilidadesCount,
  onChange,
}: ProductFormTabsProps) {
  const tabs: { id: ActiveTab; label: string }[] = [
    { id: "geral", label: "📝 Informações Gerais & Fotos" },
    { id: "estoque", label: `📦 Estoque por CD (${estoqueTotal})` },
    { id: "descontos", label: `🏷️ Descontos Volume (${descontosCount})` },
    { id: "compatibilidades", label: `🔗 Compatibilidade (${compatibilidadesCount})` },
  ];

  return (
    <div className="flex border-b border-slate-200 gap-2">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={`pb-2.5 px-3 text-xs font-bold transition-all cursor-pointer border-b-2 ${
            activeTab === tab.id
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
