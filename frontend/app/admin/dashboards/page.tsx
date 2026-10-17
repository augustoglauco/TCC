"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import DynamicChartCard, { type AdminChartData } from "@/components/admin/DynamicChartCard";
import CreateChartModal from "@/components/admin/CreateChartModal";
import {
  deleteAdminChart,
  fetchAdminCharts,
  refreshAdminChart,
  updateAdminChart,
} from "@/lib/api/charts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";
import { DashboardsHeader } from "./DashboardsHeader";
import { DashboardsEmptyState } from "./DashboardsEmptyState";

export default function AdminDashboardsPage() {
  const user = useAuthStore((s) => s.user);
  const token = useAuthStore((s) => s.token);
  const openChat = useChatStore((s) => s.open);

  const hasHydrated = useEstaNoCliente();
  const [charts, setCharts] = useState<AdminChartData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterTab, setFilterTab] = useState<"todos" | "fixados">("todos");
  const [isRefreshingAll, setIsRefreshingAll] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";

  // `carregando` deriva de quem realmente carrega: antes do hydrate sempre
  // mostra esqueleto; depois, so enquanto um admin com token esta buscando.
  // Era isso que o `else { setLoading(false) }` dentro do efeito fazia — e
  // derivar remove de vez o caso do visitante nao-admin preso no esqueleto
  // quando o efeito nao re-roda (ver comentario do efeito abaixo).
  const carregando = loading && (!hasHydrated || (isAdmin && !!token));

  // Nao toca estado antes do primeiro `await`: este loader e chamado de
  // dentro de um efeito, onde setState sincrono dispara render em cascata
  // (react-hooks/set-state-in-effect). Quem chama por evento liga o spinner
  // no proprio handler.
  const loadData = useCallback(async () => {
    if (!token) return;
    try {
      const data = await fetchAdminCharts(token);
      setCharts(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível carregar os gráficos.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    // Antes do hydrate do zustand persist, `user`/`token` ainda são os
    // valores iniciais (null) independente de haver sessão salva — decidir
    // aqui destravaria a tela cedo demais para um admin de verdade. Mas uma
    // vez hidratado, se o visitante não é admin (ou não está logado),
    // `isAdmin`/`token` nunca mais mudam sozinhos — sem `hasHydrated` na
    // lista de dependências, este efeito nunca rodava de novo pra aplicar
    // esse caso, e a página ficava presa no esqueleto de carregamento pra
    // sempre (achado ao vivo: "fica rendering" pra qualquer visitante
    // não-admin).
    if (!hasHydrated) return;
    if (isAdmin && token) {
      // Falso positivo: `loadData` so toca estado depois de
      // `await fetchAdminCharts` (funcao `async` importada), logo nao ha
      // setState sincrono. A regra nao resolve a assincronia de funcoes
      // importadas e assume o pior caso.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void loadData();
    }
  }, [hasHydrated, isAdmin, token, loadData]);

  useEffect(() => {
    const handleRefresh = () => {
      if (token) {
        setLoading(true);
        setError(null);
        void loadData();
      }
    };
    const handleVisibility = () => {
      if (document.visibilityState === "visible" && token) {
        setLoading(true);
        void loadData();
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
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar gráfico.");
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
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao alternar fixação.");
    }
  };

  const handleEditTitle = async (id: string, novoTitulo: string) => {
    if (!token) return;
    try {
      const updated = await updateAdminChart(id, { titulo: novoTitulo }, token);
      setCharts((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao renomear gráfico.");
    }
  };

  const handleDelete = async (id: string) => {
    if (!token) return;
    if (!window.confirm("Deseja realmente remover este gráfico do painel?")) return;
    try {
      await deleteAdminChart(id, token);
      setCharts((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao excluir gráfico.");
    }
  };

  const handleChartCreated = (newChart: AdminChartData) => {
    setCharts((prev) => [newChart, ...prev]);
  };

  if (hasHydrated && !isAdmin && !carregando) {
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

  const displayedCharts = filterTab === "fixados" ? charts.filter((c) => c.fixado) : charts;

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
      <DashboardsHeader
        chartsCount={charts.length}
        isRefreshingAll={isRefreshingAll}
        onRefreshAll={handleRefreshAll}
        onOpenCreate={() => setIsCreateModalOpen(true)}
        onOpenChat={openChat}
      />

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
      {carregando ? (
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
        <DashboardsEmptyState
          onOpenCreate={() => setIsCreateModalOpen(true)}
          onOpenChat={openChat}
        />
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

      <CreateChartModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreated={handleChartCreated}
      />
    </main>
  );
}
