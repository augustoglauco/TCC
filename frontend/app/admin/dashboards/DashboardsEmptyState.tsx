"use client";

import React from "react";

interface DashboardsEmptyStateProps {
  onOpenCreate: () => void;
  onOpenChat: () => void;
}

export function DashboardsEmptyState({ onOpenCreate, onOpenChat }: DashboardsEmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-2xs">
      <span className="text-4xl">📊</span>
      <h2 className="mt-3 text-lg font-bold text-slate-800">Nenhum gráfico disponível</h2>
      <p className="mt-1 max-w-md text-sm text-slate-500">
        Você ainda não possui gráficos salvos neste filtro. Peça um gráfico ao assistente
        diretamente no chat para que ele apareça aqui permanentemente.
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          onClick={onOpenCreate}
          className="rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
        >
          ➕ Criar Gráfico Manualmente
        </button>
        <button
          type="button"
          onClick={onOpenChat}
          className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          &quot;Gere um gráfico de vendas por categoria&quot;
        </button>
        <button
          type="button"
          onClick={onOpenChat}
          className="rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
        >
          &quot;Mostre o estoque por centro de distribuição&quot;
        </button>
      </div>
    </div>
  );
}
