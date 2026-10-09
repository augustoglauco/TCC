"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { fetchAiUsageMetrics, AiUsageReport, GetMetricsParams } from "@/lib/api/metrics";
import { formatarDataPtBr } from "@/lib/format/metricas";
import { SecaoPorOrigem } from "@/components/admin/metricas/SecaoPorOrigem";
import { SecaoPorAmbiente } from "@/components/admin/metricas/SecaoPorAmbiente";
import { TabelaPorModelo } from "@/components/admin/metricas/TabelaPorModelo";
import { TabelaPorOperacao } from "@/components/admin/metricas/TabelaPorOperacao";
import { TabelaDiaria } from "@/components/admin/metricas/TabelaDiaria";

function RefreshIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
      <path d="M3 21v-5h5" />
    </svg>
  );
}

export default function AdminMetricasPage() {
  const currentUser = useAuthStore((state) => state.user);
  const token = useAuthStore((state) => state.token);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [period, setPeriod] = useState<"today" | "7d" | "30d" | "all" | "custom">("7d");
  const [selectedDate, setSelectedDate] = useState<string>(() =>
    new Date().toLocaleDateString("en-CA")
  );
  const [data, setData] = useState<AiUsageReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const dateInputRef = useRef<HTMLInputElement | null>(null);
  const { toasts, showToast, dismissToast } = useToast();
  // Achado da revisão de 2026-10-04: sem isto, uma requisição mais antiga
  // (ex.: "Hoje") que demora mais que uma mais nova (ex.: "7 Dias") podia
  // resolver depois e sobrescrever a tela com dados de um período que não
  // é mais o selecionado. Só a resposta da requisição MAIS RECENTE aplica
  // seu resultado.
  const requestIdRef = useRef(0);

  const carregarMetricas = useCallback(
    async (
      p: "today" | "7d" | "30d" | "all" | "custom",
      isManual = false,
      dateParam?: string
    ) => {
      if (!token) return;
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setError(null);
      const startTime = Date.now();
      try {
        const targetDate = dateParam ?? selectedDate;
        const params: GetMetricsParams = {
          period: p,
          ...(p === "custom" && targetDate
            ? { startDate: targetDate, endDate: targetDate }
            : {}),
        };
        const res = await fetchAiUsageMetrics(token, params);
        if (requestId !== requestIdRef.current) return;
        setData(res);
        setLastUpdated(new Date());
        if (isManual) {
          const elapsed = Date.now() - startTime;
          if (elapsed < 400) {
            await new Promise((resolve) => setTimeout(resolve, 400 - elapsed));
          }
          showToast("Métricas atualizadas com sucesso!", "success");
        }
      } catch (err: unknown) {
        if (requestId !== requestIdRef.current) return;
        const msg = err instanceof Error ? err.message : "Erro ao carregar métricas.";
        setError(msg);
        if (isManual) {
          showToast(msg, "error");
        }
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    },
    [selectedDate, showToast, token]
  );

  useEffect(() => {
    if (isCurrentAdmin && token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      void carregarMetricas(period, false, selectedDate);
    }
  }, [isCurrentAdmin, token, period, selectedDate, carregarMetricas]);

  const handleDateChange = (newDate: string) => {
    if (newDate) {
      setSelectedDate(newDate);
      if (period !== "custom") {
        setPeriod("custom");
      }
    }
  };

  if (!currentUser || !isCurrentAdmin) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-3xl font-bold shadow-xs border border-rose-200">
          🔒
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Acesso Restrito ao Administrador</h1>
          <p className="mt-2 text-sm text-slate-600">
            Você precisa estar autenticado como Administrador para visualizar relatórios de tokens,
            custos e chats encerrados.
          </p>
        </div>
        <div className="pt-2">
          <Link
            href="/conta/login"
            className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            Fazer Login como Administrador
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:py-8 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-2xl">📊</span>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Métricas & Custos de IA
            </h1>
            <button
              type="button"
              onClick={() => void carregarMetricas(period, true)}
              disabled={loading}
              title="Atualizar métricas"
              aria-label="Atualizar métricas"
              className="group inline-flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-2xs hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <RefreshIcon
                className={`h-4 w-4 ${loading ? "animate-spin text-blue-600" : "text-slate-500 group-hover:text-slate-800"}`}
              />
            </button>
          </div>
          <p className="mt-1.5 text-xs sm:text-sm text-slate-600 max-w-3xl">
            Acompanhamento de consumo de tokens (locais vs externos), custos financeiros segregados
            (entrada/saída) e relatórios de atendimentos encerrados.
          </p>
        </div>

        {/* Filtros de Período */}
        <div className="flex flex-col sm:items-end gap-2 self-start sm:self-auto shrink-0">
          <div className="flex items-center gap-2 flex-nowrap overflow-x-auto max-w-full">
            <div className="flex items-center gap-1 sm:gap-1.5 rounded-xl border border-slate-200 bg-white p-1 shadow-2xs shrink-0 flex-nowrap">
              <label
                className={`relative inline-flex items-center gap-1.5 rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap cursor-pointer select-none focus-within:ring-2 focus-within:ring-blue-500 ${
                  period === "custom"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
                title="Filtrar por data no calendário"
              >
                <span aria-hidden="true">📅</span>
                <span>
                  {period === "custom" && selectedDate
                    ? formatarDataPtBr(selectedDate)
                    : "Calendário"}
                </span>
                <input
                  ref={dateInputRef}
                  type="date"
                  max={new Date().toLocaleDateString("en-CA")}
                  value={selectedDate}
                  onChange={(e) => handleDateChange(e.target.value)}
                  onClick={(e) => {
                    if (period !== "custom") {
                      setPeriod("custom");
                    }
                    try {
                      (e.target as HTMLInputElement).showPicker?.();
                    } catch {}
                  }}
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
                  aria-label="Escolher data específica"
                />
              </label>
              <button
                type="button"
                onClick={() => setPeriod("today")}
                className={`rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap ${
                  period === "today"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Hoje
              </button>
              <button
                type="button"
                onClick={() => setPeriod("7d")}
                className={`rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap ${
                  period === "7d"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                7 Dias
              </button>
              <button
                type="button"
                onClick={() => setPeriod("30d")}
                className={`rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap ${
                  period === "30d"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                30 Dias
              </button>
              <button
                type="button"
                onClick={() => setPeriod("all")}
                className={`rounded-lg px-2.5 sm:px-3 py-1.5 text-xs font-semibold transition-colors shrink-0 whitespace-nowrap ${
                  period === "all"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Tudo
              </button>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {period === "custom" && (
              <span className="text-[11px] text-blue-700 font-semibold bg-blue-50 px-2 py-0.5 rounded-md border border-blue-200">
                Visualizando dia: {formatarDataPtBr(selectedDate)}
              </span>
            )}
            {lastUpdated && (
              <span className="text-[11px] text-slate-500 font-medium">
                Última atualização: {lastUpdated.toLocaleTimeString("pt-BR")}
              </span>
            )}
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-sm text-slate-600">
        <span>
          Chats encerrados no período:{" "}
          <strong data-testid="chats-encerrados" className="text-slate-900">
            {data?.atendimento.chats_encerrados ?? 0}
          </strong>
        </span>
        {data && data.totais.chamadas_sem_custo_medido > 0 ? (
          <span className="text-amber-700">
            Chamadas sem custo medido:{" "}
            <strong data-testid="sem-custo-medido">
              {data.totais.chamadas_sem_custo_medido}
            </strong>
          </span>
        ) : null}
      </div>

      {data ? (
        <div className="space-y-6">
          <SecaoPorOrigem linhas={data.por_origem} />
          <SecaoPorAmbiente linhas={data.por_ambiente} totais={data.totais} />
          <TabelaPorModelo linhas={data.por_modelo} />
          <TabelaPorOperacao linhas={data.por_operacao} />
          <TabelaDiaria dias={data.diario} />
        </div>
      ) : null}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
