"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DynamicChartCard, { type AdminChartData } from "@/components/admin/DynamicChartCard";
import {
  deleteAdminChart,
  fetchAdminCharts,
  refreshAdminChart,
  updateAdminChart,
} from "@/lib/api/charts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";

export default function AdminDashboardsPage() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const openChat = useChatStore((s) => s.open);

  const [hasHydrated, setHasHydrated] = useState(false);
  const [charts, setCharts] = useState<AdminChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterTab, setFilterTab] = useState<"todos" | "fixados">("todos");
  const [isRefreshingAll, setIsRefreshingAll] = useState(false);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  useEffect(() => {
    setHasHydrated(true);
  }, []);

  const loadData = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminCharts(token);
      setCharts(data);
    } catch (err: any) {
      setError(err?.message || "Não foi possível carregar os gráficos.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (isAdmin && token) {
      loadData();
    } else if (hasHydrated && !isAdmin) {
      setLoading(false);
    }
  }, [isAdmin, token, loadData]);

  useEffect(() => {
    const handleRefresh = () => {
      if (token) {
        loadData();
      }
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && token) {
        loadData();
      }
    };

    window.addEventListener("refresh_admin_charts", handleRefresh);
    window.addEventListener("focus", handleRefresh);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      window.removeEventListener("refresh_admin_charts", handleRefresh);
      window.removeEventListener("focus", handleRefresh);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [token, loadData]);

  const handleRefresh = async (id: string) => {
    if (!token) return;
    try {
      const updated = await refreshAdminChart(id, token);
      setCharts((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err: any) {
      alert(err?.message || "Erro ao atualizar gráfico.");
    }
  };

  const handleRefreshAll = async () => {
    if (!token || charts.length === 0) return;
    setIsRefreshingAll(true);
    try {
      await Promise.all(
        charts.map(async (c) => {
          try {
            const updated = await refreshAdminChart(c.id, token);
            setCharts((prev) => prev.map((item) => (item.id === c.id ? updated : item)));
          } catch {
            // continua para os outros
          }
        }),
      );
    } finally {
      setIsRefreshingAll(false);
    }
  };

  const handleTogglePin = async (id: string, fixado: boolean) => {
    if (!token) return;
    try {
      const updated = await updateAdminChart(id, { fixado }, token);
      setCharts((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err: any) {
      alert(err?.message || "Erro ao alternar fixação.");
    }
  };

  const handleEditTitle = async (id: string, novoTitulo: string) => {
    if (!token) return;
    try {
      const updated = await updateAdminChart(id, { titulo: novoTitulo }, token);
      setCharts((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err: any) {
      alert(err?.message || "Erro ao renomear gráfico.");
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    if (!window.confirm("Deseja realmente remover este gráfico do painel?")) return;
    try {
      await deleteAdminChart(id, token);
      setCharts((prev) => prev.filter((c) => c.id !== id));
    } catch (err: any) {
      alert(err?.message || "Erro ao excluir gráfico.");
    }
  };

  if (hasHydrated && !isAdmin && !loading) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-16 text-center">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8">
          <span className="text-4xl">🔒</span>
          <h1 className="mt-3 text-xl font-bold text-red-800">Acesso Restrito</h1>
          <p className="mt-2 text-sm text-red-600">
            Você precisa estar logado como Administrador para visualizar e gerenciar Dashboards.
          </p>
          <div className="mt-6">
            <Link
              href="/conta/login"
              className="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-red-700 transition-colors"
            >
              Fazer Login como Administrador
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const displayedCharts =
    filterTab === "fixados" ? charts.filter((c) => c.fixado) : charts;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      {/* Breadcrumb */}
      <nav className="mb-4 flex items-center gap-2 text-xs font-medium text-slate-500">
        <Link href="/" className="hover:text-blue-600 transition-colors">
          Início
        </Link>
        <span>/</span>
        <span>Administração</span>
        <span>/</span>
        <span className="font-semibold text-slate-800">Dashboards</span>
      </nav>

      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">📈</span>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Dashboards & Gráficos
            </h1>
          </div>
          <p className="mt-1 text-sm text-slate-500">
            Painel permanente de gráficos e visualizações geradas pelo Administrador no Chat.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={handleRefreshAll}
            disabled={isRefreshingAll || charts.length === 0}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:text-blue-600 disabled:opacity-50 transition-colors"
          >
            <span className={isRefreshingAll ? "animate-spin" : ""}>🔄</span>
            <span>Atualizar Todos</span>
          </button>

          <button
            type="button"
            onClick={() => openChat()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 transition-colors"
          >
            <span>💬</span>
            <span>Pedir Novo Gráfico</span>
          </button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="mb-6 flex items-center justify-between border-b border-slate-200 pb-2">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setFilterTab("todos")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              filterTab === "todos"
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            Todos ({charts.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterTab("fixados")}
            className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
              filterTab === "fixados"
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            📌 Apenas Fixados ({charts.filter((c) => c.fixado).length})
          </button>
        </div>

        <span className="text-xs text-slate-400">
          {displayedCharts.length} gráfico(s) exibido(s)
        </span>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-80 animate-pulse rounded-2xl border border-slate-200 bg-slate-50"
            />
          ))}
        </div>
      ) : displayedCharts.length === 0 ? (
        /* Empty State */
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-2xs">
          <span className="text-4xl">📊</span>
          <h2 className="mt-3 text-lg font-bold text-slate-800">
            Nenhum gráfico disponível
          </h2>
          <p className="mt-1 max-w-md text-sm text-slate-500">
            Você ainda não possui gráficos salvos neste filtro. Peça um gráfico ao assistente
            diretamente no chat para que ele apareça aqui permanentemente.
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={() => openChat()}
              className="rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 hover:bg-blue-100 transition-colors"
            >
              "Gere um gráfico de vendas por categoria"
            </button>
            <button
              type="button"
              onClick={() => openChat()}
              className="rounded-lg bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors"
            >
              "Mostre o estoque por centro de distribuição"
            </button>
          </div>
        </div>
      ) : (
        /* Charts Grid */
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
      )}
    </main>
  );
}
