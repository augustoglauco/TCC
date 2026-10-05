"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { ToastStack, useToast } from "@/components/ui/Toast";
import {
  fetchTokenCostMetrics,
  TokenCostMetricsResponse,
  GetMetricsParams,
  DailyMetric,
} from "@/lib/api/metrics";

function formatarDataPtBr(isoDate: string): string {
  if (!isoDate) return "";
  const parts = isoDate.split("-");
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return isoDate;
}

function obterDiaSemanaPtBr(isoDate: string): string {
  if (!isoDate) return "";
  try {
    const parts = isoDate.split("-");
    if (parts.length === 3) {
      const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
      const dias = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
      return dias[d.getDay()] || "";
    }
  } catch {}
  return "";
}

function preencherLinhasDetalhamento(
  daily: DailyMetric[],
  period: "today" | "7d" | "30d" | "all" | "custom",
  selectedDate: string,
): DailyMetric[] {
  if (period === "custom") {
    if (daily.length > 0) return daily;
    return [
      {
        date: selectedDate,
        closed_chats_count: 0,
        internal_prompt_tokens: 0,
        internal_completion_tokens: 0,
        external_prompt_tokens: 0,
        external_completion_tokens: 0,
        cost_prompt_usd: 0,
        cost_completion_usd: 0,
        total_cost_usd: 0,
        vision_calls_count: 0,
        vision_cost_usd: 0,
        ingestion_calls_count: 0,
        ingestion_tokens: 0,
        ingestion_cost_usd: 0,
      },
    ];
  }

  if (period === "today") {
    if (daily.length > 0) return daily;
    const hojeStr = new Date().toLocaleDateString("en-CA");
    return [
      {
        date: hojeStr,
        closed_chats_count: 0,
        internal_prompt_tokens: 0,
        internal_completion_tokens: 0,
        external_prompt_tokens: 0,
        external_completion_tokens: 0,
        cost_prompt_usd: 0,
        cost_completion_usd: 0,
        total_cost_usd: 0,
        vision_calls_count: 0,
        vision_cost_usd: 0,
        ingestion_calls_count: 0,
        ingestion_tokens: 0,
        ingestion_cost_usd: 0,
      },
    ];
  }

  const numDias = period === "30d" ? 30 : 7;
  const mapExistente = new Map<string, DailyMetric>();
  for (const item of daily) {
    mapExistente.set(item.date, item);
  }

  // Base para contagem: usa a data mais recente retornada ou a data atual
  const baseDate = daily.length > 0
    ? new Date(daily[0].date + "T12:00:00")
    : new Date();

  const resultado: DailyMetric[] = [];
  const datasInseridas = new Set<string>();

  for (let i = 0; i < numDias; i++) {
    const d = new Date(baseDate);
    d.setDate(baseDate.getDate() - i);
    const ano = d.getFullYear();
    const mes = String(d.getMonth() + 1).padStart(2, "0");
    const dia = String(d.getDate()).padStart(2, "0");
    const iso = `${ano}-${mes}-${dia}`;
    datasInseridas.add(iso);

    if (mapExistente.has(iso)) {
      resultado.push(mapExistente.get(iso)!);
    } else {
      resultado.push({
        date: iso,
        closed_chats_count: 0,
        internal_prompt_tokens: 0,
        internal_completion_tokens: 0,
        external_prompt_tokens: 0,
        external_completion_tokens: 0,
        cost_prompt_usd: 0,
        cost_completion_usd: 0,
        total_cost_usd: 0,
        vision_calls_count: 0,
        vision_cost_usd: 0,
        ingestion_calls_count: 0,
        ingestion_tokens: 0,
        ingestion_cost_usd: 0,
      });
    }
  }

  // Inclui qualquer outro dia retornado pelo backend que não esteja nos primeiros N dias
  for (const item of daily) {
    if (!datasInseridas.has(item.date)) {
      resultado.push(item);
    }
  }

  return resultado.sort((a, b) => b.date.localeCompare(a.date));
}

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
  const [data, setData] = useState<TokenCostMetricsResponse | null>(null);
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
        const res = await fetchTokenCostMetrics(token, params);
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

  const summary = data?.summary;
  const rawDaily = data?.daily_breakdown ?? [];
  const daily = preencherLinhasDetalhamento(rawDaily, period, selectedDate);

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

      {error && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 shadow-2xs"
        >
          <p className="font-semibold">{error}</p>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {/* Card 1: Tokens Internos */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Tokens Internos (GPU Local)
              </span>
              <span className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200">
                R$ 0,00
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-slate-900 tracking-tight">
              {summary
                ? (
                    summary.total_internal_prompt_tokens +
                    summary.total_internal_completion_tokens
                  ).toLocaleString("pt-BR")
                : "0"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5 flex justify-between">
            <span>Entrada: {summary?.total_internal_prompt_tokens.toLocaleString("pt-BR") ?? 0}</span>
            <span>Saída: {summary?.total_internal_completion_tokens.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 2: Tokens Externos */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Tokens Externos (OpenRouter)
              </span>
              <span className="rounded-md bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 border border-blue-200">
                Nuvem
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-slate-900 tracking-tight">
              {summary
                ? (
                    summary.total_external_prompt_tokens +
                    summary.total_external_completion_tokens
                  ).toLocaleString("pt-BR")
                : "0"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5 flex justify-between">
            <span>Entrada: {summary?.total_external_prompt_tokens.toLocaleString("pt-BR") ?? 0}</span>
            <span>Saída: {summary?.total_external_completion_tokens.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 3: Visão Computacional */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Visão Computacional (Imagens)
              </span>
              <span className="rounded-md bg-sky-50 px-1.5 py-0.5 text-[10px] font-semibold text-sky-700 border border-sky-200">
                Multimodal
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-sky-700 tracking-tight">
              ${summary?.total_vision_cost_usd !== undefined ? summary.total_vision_cost_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5 flex justify-between">
            <span>{`Imagens: ${summary?.total_vision_calls?.toLocaleString("pt-BR") ?? 0}`}</span>
            <span>Tokens: {summary?.total_vision_tokens?.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 4: Ingestão & Dados */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Ingestão & Dados (Crawler/Catálogo)
              </span>
              <span className="rounded-md bg-teal-50 px-1.5 py-0.5 text-[10px] font-semibold text-teal-700 border border-teal-200">
                Backoffice
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-teal-700 tracking-tight">
              ${summary?.total_ingestion_cost_usd !== undefined ? summary.total_ingestion_cost_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5 flex justify-between">
            <span>{`Operações: ${summary?.total_ingestion_calls?.toLocaleString("pt-BR") ?? 0}`}</span>
            <span>{`Tokens: ${summary?.total_ingestion_tokens?.toLocaleString("pt-BR") ?? 0}`}</span>
          </p>
        </div>

        {/* Card 5: Custo Total */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo Total Geral (Infraestrutura)
              </span>
              <span className="rounded-md bg-purple-50 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700 border border-purple-200">
                USD
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-purple-700 tracking-tight">
              ${summary?.grand_total_cost_usd !== undefined
                ? summary.grand_total_cost_usd.toFixed(4)
                : ((summary?.total_cost_usd || 0) + (summary?.total_ingestion_cost_usd || 0)).toFixed(4)}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5 flex justify-between">
            <span>{`Atendimento: $${summary?.total_cost_usd?.toFixed(4) ?? "0.0000"}`}</span>
            <span>{`Ingestão: $${summary?.total_ingestion_cost_usd?.toFixed(4) ?? "0.0000"}`}</span>
          </p>
        </div>

        {/* Card 6: Custo Entrada */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo de Entrada (Prompt)
              </span>
              <span className="rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700 border border-indigo-200">
                Contexto
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-slate-900 tracking-tight">
              ${summary?.total_cost_prompt_usd !== undefined ? summary.total_cost_prompt_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5">
            Perguntas, sistema e RAG enviados
          </p>
        </div>

        {/* Card 7: Custo Saída */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo de Saída (Resposta)
              </span>
              <span className="rounded-md bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 border border-amber-200">
                Geração
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-slate-900 tracking-tight">
              ${summary?.total_cost_completion_usd !== undefined ? summary.total_cost_completion_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5">
            Tokens de respostas gerados na nuvem
          </p>
        </div>

        {/* Card 8: Chats Encerrados */}
        <div className="rounded-xl border border-slate-200 bg-white p-3.5 sm:p-4 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Chats Encerrados
              </span>
              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200">
                Sessões
              </span>
            </div>
            <p className="mt-1.5 text-xl font-bold text-slate-900 tracking-tight">
              {summary?.total_closed_chats ?? 0}
            </p>
          </div>
          <p className="mt-1.5 text-[11px] text-slate-500 border-t border-slate-100 pt-1.5">
            Finalizados manualmente ou inatividade
          </p>
        </div>
      </div>

      {/* Tabela de Detalhamento Diário */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="border-b border-slate-200 bg-slate-50/70 px-5 py-3.5 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900 flex flex-wrap items-center gap-x-2 gap-y-1">
              <span>Detalhamento Diário dos Atendimentos Encerrados</span>
              <span className="rounded-full bg-slate-100 text-slate-600 px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap">
                {daily.length} {daily.length === 1 ? "dia" : "dias"}
              </span>
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              <span>Agrupamento diário baseado na data de encerramento da conversa.</span>
              {period === "custom" && (
                <span className="whitespace-nowrap font-medium text-slate-700 ml-1">
                  (Filtrando dia {formatarDataPtBr(selectedDate)})
                </span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void carregarMetricas(period, true)}
            className="group flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors shadow-2xs disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            disabled={loading}
            aria-label="Atualizar tabela de métricas"
            title="Atualizar dados da tabela"
          >
            <RefreshIcon
              className={`h-3.5 w-3.5 ${loading ? "animate-spin text-blue-600" : "text-slate-500 group-hover:text-slate-800"}`}
            />
            <span>{loading ? "Atualizando..." : "Atualizar"}</span>
          </button>
        </div>

        <div className="overflow-x-auto min-h-[360px] max-h-[580px] overflow-y-auto">
          <table className="w-full text-left text-xs text-slate-700 border-collapse min-w-[1000px]">
            <thead className="sticky top-0 z-20 border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500 shadow-2xs">
              <tr>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[130px] align-bottom">
                  <span>Data</span>
                  <div className="absolute top-full left-0 mt-2 hidden group-hover:block z-30 w-44 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Data do encerramento da conversa
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[110px] align-bottom">
                  <span className="inline-block">
                    <span>Chats</span>{" "}
                    <span className="block whitespace-nowrap">Encerrados</span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Total de atendimentos finalizados no dia
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[130px] align-bottom">
                  <span className="inline-block">
                    <span>Tokens Internos</span>{" "}
                    <span className="block whitespace-nowrap font-normal text-slate-400 text-[10px] tracking-normal">
                      (Entrada / Saída)
                    </span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Consumo de LLM em infraestrutura própria (Ollama Local)
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[130px] align-bottom">
                  <span className="inline-block">
                    <span>Tokens Externos</span>{" "}
                    <span className="block whitespace-nowrap font-normal text-slate-400 text-[10px] tracking-normal">
                      (Entrada / Saída)
                    </span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Consumo de modelos na nuvem pagando por token
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[120px] align-bottom">
                  <span className="inline-block">
                    <span>Visão</span>{" "}
                    <span className="block whitespace-nowrap font-normal text-slate-400 text-[10px] tracking-normal">
                      (Imagens / Custo)
                    </span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Chamadas para modelo multimodal de identificação de imagens
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[120px] align-bottom">
                  <span className="inline-block">
                    <span>Ingestão</span>{" "}
                    <span className="block whitespace-nowrap font-normal text-slate-400 text-[10px] tracking-normal">
                      (Op / Custo)
                    </span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Processamento de documentos e crawler de catálogo de produtos
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[100px] align-bottom">
                  <span className="inline-block">
                    <span>Custo</span>{" "}
                    <span className="block whitespace-nowrap">Entrada</span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Custo em USD dos tokens de Entrada (Prompt/RAG/Contexto)
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 relative group cursor-help min-w-[100px] align-bottom">
                  <span className="inline-block">
                    <span>Custo</span>{" "}
                    <span className="block whitespace-nowrap">Saída</span>
                  </span>
                  <div className="absolute top-full left-1/2 -translate-x-1/2 mt-2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight">
                    Custo em USD dos tokens de Saída (Completion/Respostas)
                  </div>
                </th>
                <th scope="col" className="px-5 py-3 text-right relative group cursor-help min-w-[100px] align-bottom">
                  <span className="inline-block text-right">
                    <span>Custo</span>{" "}
                    <span className="block whitespace-nowrap">Total</span>
                  </span>
                  <div className="absolute top-full right-0 mt-2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none normal-case font-normal leading-tight text-left">
                    Consolidação total financeira em USD (LLM + Visão + Ingestão)
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {daily.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-5 py-8 text-center text-slate-400">
                    {loading
                      ? "Carregando métricas..."
                      : period === "custom"
                      ? `Nenhum atendimento encerrado registrado no dia ${formatarDataPtBr(selectedDate)}.`
                      : "Nenhum chat encerrado registrado no período selecionado."}
                  </td>
                </tr>
              ) : (
                daily.map((item, index) => {
                  const isFirstRow = index === 0;
                  return (
                  <tr key={item.date} className="hover:bg-slate-50/80 transition-colors">
                    {/* Coluna 1: Data */}
                    <td className="px-5 py-3.5 align-top whitespace-nowrap min-w-[140px]">
                      <div className="font-semibold text-slate-900 text-xs sm:text-sm tracking-tight">
                        {formatarDataPtBr(item.date)}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5 font-medium flex items-center gap-1">
                        <span>{obterDiaSemanaPtBr(item.date)}</span>
                        <span>•</span>
                        <span className="font-mono">{item.date}</span>
                      </div>
                    </td>

                    {/* Coluna 2: Chats Encerrados */}
                    <td className="px-5 py-3.5 align-top whitespace-nowrap min-w-[120px]">
                      <div className="flex flex-col items-start gap-0.5">
                        <span className="inline-flex items-center justify-center rounded-full bg-slate-100 px-2.5 py-0.5 font-bold text-slate-800">
                          {item.closed_chats_count}
                        </span>
                        <span className="text-[10px] text-slate-400">concluídos</span>
                      </div>
                    </td>

                    {/* Coluna 3: Tokens Internos */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[150px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-bold text-slate-900">
                          {`${(item.internal_prompt_tokens + item.internal_completion_tokens).toLocaleString("pt-BR")} tokens`}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {`Entrada: ${item.internal_prompt_tokens.toLocaleString("pt-BR")}`}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {`Saída: ${item.internal_completion_tokens.toLocaleString("pt-BR")}`}
                        </span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-emerald-400">GPU Local (Ollama)</div>
                        <div>{`Prompt Interno: ${item.internal_prompt_tokens.toLocaleString("pt-BR")} tokens`}</div>
                        <div>{`Completion Interno: ${item.internal_completion_tokens.toLocaleString("pt-BR")} tokens`}</div>
                        <div className="text-[10px] text-slate-400 mt-1">Custo infra: R$ 0,00 (Local)</div>
                      </div>
                    </td>

                    {/* Coluna 4: Tokens Externos */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[150px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-bold text-slate-900">
                          {`${(item.external_prompt_tokens + item.external_completion_tokens).toLocaleString("pt-BR")} tokens`}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {`Entrada: ${item.external_prompt_tokens.toLocaleString("pt-BR")}`}
                        </span>
                        <span className="text-[11px] text-slate-500">
                          {`Saída: ${item.external_completion_tokens.toLocaleString("pt-BR")}`}
                        </span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-blue-400">OpenRouter (Nuvem)</div>
                        <div>{`Prompt Externo: ${item.external_prompt_tokens.toLocaleString("pt-BR")} tokens`}</div>
                        <div>{`Completion Externo: ${item.external_completion_tokens.toLocaleString("pt-BR")} tokens`}</div>
                        <div className="text-[10px] text-slate-400 mt-1">Segregação por modelo de IA</div>
                      </div>
                    </td>

                    {/* Coluna 5: Visão */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[120px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-bold text-sky-700">
                          {(item.vision_calls_count ?? 0) === 1
                            ? "1 imagem"
                            : `${item.vision_calls_count ?? 0} imagens`}
                        </span>
                        <span className="text-[11px] font-mono text-sky-600">
                          {`($${item.vision_cost_usd !== undefined ? item.vision_cost_usd.toFixed(4) : "0.0000"})`}
                        </span>
                        <span className="text-[10px] text-slate-400">Multimodal</span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-sky-400">Visão Computacional</div>
                        <div>{`Imagens Processadas: ${item.vision_calls_count ?? 0}`}</div>
                        <div>{`Custo Visão: $${item.vision_cost_usd !== undefined ? item.vision_cost_usd.toFixed(4) : "0.0000"}`}</div>
                      </div>
                    </td>

                    {/* Coluna 6: Ingestão */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[130px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-bold text-teal-700">
                          {`${item.ingestion_calls_count ?? 0} op${(item.ingestion_calls_count ?? 0) === 1 ? "" : "s"}`}
                        </span>
                        {(item.ingestion_tokens ?? 0) > 0 && (
                          <span className="text-[11px] font-semibold text-slate-700">
                            {`${(item.ingestion_tokens ?? 0).toLocaleString("pt-BR")} tokens`}
                          </span>
                        )}
                        <span className="text-[11px] font-mono text-teal-600">
                          {`($${item.ingestion_cost_usd !== undefined ? item.ingestion_cost_usd.toFixed(4) : "0.0000"})`}
                        </span>
                        <span className="text-[10px] text-slate-400">RAG / Catálogo</span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-52 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-teal-400">Ingestão & Dados</div>
                        <div>{`Total Operações: ${item.ingestion_calls_count ?? 0}`}</div>
                        <div>{`Tokens Ingestão: ${(item.ingestion_tokens ?? 0).toLocaleString("pt-BR")}`}</div>
                        <div>{`Custo Ingestão: $${item.ingestion_cost_usd !== undefined ? item.ingestion_cost_usd.toFixed(4) : "0.0000"}`}</div>
                      </div>
                    </td>

                    {/* Coluna 7: Custo Entrada */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[110px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-mono font-bold text-indigo-700">
                          {`$${item.cost_prompt_usd.toFixed(4)}`}
                        </span>
                        <span className="text-[10px] text-slate-400">Prompt</span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-indigo-400">Custo Entrada</div>
                        <div>{`Subtotal Entrada: $${item.cost_prompt_usd.toFixed(4)}`}</div>
                      </div>
                    </td>

                    {/* Coluna 8: Custo Saída */}
                    <td className="px-5 py-3.5 align-top relative group whitespace-nowrap min-w-[110px]">
                      <div className="flex flex-col space-y-0.5">
                        <span className="font-mono font-bold text-amber-700">
                          {`$${item.cost_completion_usd.toFixed(4)}`}
                        </span>
                        <span className="text-[10px] text-slate-400">Completion</span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} left-1/2 -translate-x-1/2 hidden group-hover:block z-30 w-48 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-amber-400">Custo Saída</div>
                        <div>{`Subtotal Saída: $${item.cost_completion_usd.toFixed(4)}`}</div>
                      </div>
                    </td>

                    {/* Coluna 9: Custo Total */}
                    <td className="px-5 py-3.5 align-top text-right relative group whitespace-nowrap min-w-[110px]">
                      <div className="flex flex-col items-end space-y-0.5">
                        <span className="font-mono font-extrabold text-slate-900">
                          {`$${item.total_cost_usd.toFixed(4)}`}
                        </span>
                        <span className="text-[10px] text-slate-400">Consolidado</span>
                      </div>
                      {/* Bubble Tooltip */}
                      <div className={`absolute ${isFirstRow ? "top-full mt-2" : "bottom-full mb-2"} right-0 hidden group-hover:block z-30 w-56 rounded-xl bg-slate-900 text-white text-[11px] p-2.5 shadow-xl border border-slate-700 pointer-events-none leading-snug text-left`}>
                        <div className="font-semibold border-b border-slate-700 pb-1 mb-1 text-purple-400">Consolidado do Dia</div>
                        <div>{`Total Diário: $${item.total_cost_usd.toFixed(4)}`}</div>
                        <div className="text-[10px] text-slate-400 mt-1">Inclui Atendimento, Visão e Ingestão</div>
                      </div>
                    </td>
                  </tr>
                );
              })
              )}
            </tbody>
          </table>
        </div>
      </div>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
