"use client";

import React, { useState } from "react";
import Link from "next/link";
import DynamicChartCard from "@/components/admin/DynamicChartCard";
import CreateChartModal from "@/components/admin/CreateChartModal";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { DashboardsHeader } from "./DashboardsHeader";
import { DashboardsEmptyState } from "./DashboardsEmptyState";
import { DashboardsFilterTabs } from "./DashboardsFilterTabs";
import { DashboardsAcessoRestrito } from "./DashboardsAcessoRestrito";
import { useAdminCharts } from "./useAdminCharts";

function DashboardsBreadcrumb() {
  return (
    <nav className="mb-4 flex items-center gap-2 text-xs font-medium text-slate-500">
      <Link href="/" className="hover:text-blue-600 transition-colors">
        Início
      </Link>
      <span>/</span>
      <span>Administração</span>
      <span>/</span>
      <span className="font-semibold text-slate-800">Dashboards</span>
    </nav>
  );
}

function DashboardsSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {[1, 2].map((i) => (
        <div
          key={i}
          className="h-80 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
        />
      ))}
    </div>
  );
}

export default function AdminDashboardsPage() {
  const openChat = useChatStore((s) => s.open);
  const {
    charts,
    error,
    isRefreshingAll,
    isAdmin,
    hasHydrated,
    carregando,
    handleRefresh,
    handleRefreshAll,
    handleTogglePin,
    handleEditTitle,
    handleDelete,
    handleChartCreated,
  } = useAdminCharts();
  const [filterTab, setFilterTab] = useState<"todos" | "fixados">("todos");
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  if (hasHydrated && !isAdmin && !carregando) return <DashboardsAcessoRestrito />;

  const fixadosCount = charts.filter((c) => c.fixado).length;
  const displayedCharts = filterTab === "fixados" ? charts.filter((c) => c.fixado) : charts;
  const abrirCriacao = () => setIsCreateModalOpen(true);

  let conteudo: React.ReactNode;
  if (carregando) {
    conteudo = <DashboardsSkeleton />;
  } else if (displayedCharts.length === 0) {
    conteudo = <DashboardsEmptyState onOpenCreate={abrirCriacao} onOpenChat={openChat} />;
  } else {
    conteudo = (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {displayedCharts.map((chart) => (
          <DynamicChartCard
            key={chart.id}
            chart={chart}
            onRefresh={handleRefresh}
            onTogglePin={handleTogglePin}
            onDelete={handleDelete}
            onEditTitle={handleEditTitle}
          />
        ))}
      </div>
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <DashboardsBreadcrumb />

      <DashboardsHeader
        chartsCount={charts.length}
        isRefreshingAll={isRefreshingAll}
        onRefreshAll={handleRefreshAll}
        onOpenCreate={abrirCriacao}
        onOpenChat={openChat}
      />

      <DashboardsFilterTabs
        filterTab={filterTab}
        totalCount={charts.length}
        fixadosCount={fixadosCount}
        displayedCount={displayedCharts.length}
        onChange={setFilterTab}
      />

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {conteudo}

      <CreateChartModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={handleChartCreated}
      />
    </main>
  );
}
