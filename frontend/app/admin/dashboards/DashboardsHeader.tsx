"use client";

import React from "react";

interface DashboardsHeaderProps {
  chartsCount: number;
  isRefreshingAll: boolean;
  onRefreshAll: () => void;
  onOpenCreate: () => void;
  onOpenChat: () => void;
}

export function DashboardsHeader({
  chartsCount,
  isRefreshingAll,
  onRefreshAll,
  onOpenCreate,
  onOpenChat,
}: DashboardsHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <div className="flex items-center gap-2">
          <span className="text-2xl">📈</span>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Dashboards &amp; Gráficos
          </h1>
        </div>
        <p className="mt-1 text-sm text-slate-500">
          Painel permanente de gráficos e visualizações geradas pelo Administrador no Chat.
        </p>
      </div>

      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={onRefreshAll}
          disabled={isRefreshingAll || chartsCount === 0}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:text-blue-600 disabled:opacity-50 transition-colors"
        >
          <span className={isRefreshingAll ? "animate-spin" : ""}>🔄</span>
          <span>Atualizar Todos</span>
        </button>

        <button
          type="button"
          onClick={onOpenCreate}
          className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50 px-3.5 py-2 text-xs font-semibold text-blue-700 shadow-2xs hover:bg-blue-100 transition-colors"
        >
          <span>➕</span>
          <span>Criar Gráfico</span>
        </button>

        <button
          type="button"
          onClick={onOpenChat}
          className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 transition-colors"
        >
          <span>💬</span>
          <span>Pedir Novo Gráfico</span>
        </button>
      </div>
    </div>
  );
}
