"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { ToastStack, useToast } from "@/components/ui/Toast";
import {
  fetchTokenCostMetrics,
  TokenCostMetricsResponse,
  GetMetricsParams,
} from "@/lib/api/metrics";

function formatarDataPtBr(isoDate: string): string {
  if (!isoDate) return "";
  const parts = isoDate.split("-");
  if (parts.length === 3) {
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
  }
  return isoDate;
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

  const handleSelectPorDia = () => {
    setPeriod("custom");
    setTimeout(() => {
      try {
        dateInputRef.current?.showPicker?.();
      } catch {
        dateInputRef.current?.focus();
      }
    }, 50);
  };

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
  const daily = data?.daily_breakdown ?? [];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-12 space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-6">
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
        <div className="flex flex-col sm:items-end gap-2 self-start sm:self-auto">
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-1 shadow-2xs">
              <button
                type="button"
                onClick={() => setPeriod("today")}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
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
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
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
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
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
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors ${
                  period === "all"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                Tudo
              </button>
              <button
                type="button"
                onClick={handleSelectPorDia}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                  period === "custom"
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
                aria-label="Filtrar por dia específico"
              >
                <span>📅</span>
                <span>Por Dia</span>
              </button>
            </div>

            {/* Seletor de Data / Calendário */}
            {period === "custom" && (
              <div className="flex items-center gap-1.5 rounded-xl border border-blue-200 bg-blue-50/80 px-2.5 py-1 text-xs shadow-2xs">
                <label
                  htmlFor="filtro-data-especifica"
                  className="text-xs font-bold text-blue-900 shrink-0"
                >
                  Dia:
                </label>
                <input
                  id="filtro-data-especifica"
                  ref={dateInputRef}
                  type="date"
                  max={new Date().toLocaleDateString("en-CA")}
                  value={selectedDate}
                  onChange={(e) => handleDateChange(e.target.value)}
                  className="rounded-lg border border-blue-300 bg-white px-2 py-1 text-xs font-semibold text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer shadow-2xs"
                  aria-label="Escolher data específica"
                />
              </div>
            )}
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {/* Card 1: Tokens Internos */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Tokens Internos (GPU Local)
              </span>
              <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
                R$ 0,00
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-slate-900 tracking-tight">
              {summary
                ? (
                    summary.total_internal_prompt_tokens +
                    summary.total_internal_completion_tokens
                  ).toLocaleString("pt-BR")
                : "0"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2 flex justify-between">
            <span>Entrada: {summary?.total_internal_prompt_tokens.toLocaleString("pt-BR") ?? 0}</span>
            <span>Saída: {summary?.total_internal_completion_tokens.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 2: Tokens Externos */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Tokens Externos (OpenRouter)
              </span>
              <span className="rounded-md bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 border border-blue-200">
                Nuvem
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-slate-900 tracking-tight">
              {summary
                ? (
                    summary.total_external_prompt_tokens +
                    summary.total_external_completion_tokens
                  ).toLocaleString("pt-BR")
                : "0"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2 flex justify-between">
            <span>Entrada: {summary?.total_external_prompt_tokens.toLocaleString("pt-BR") ?? 0}</span>
            <span>Saída: {summary?.total_external_completion_tokens.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 3: Visão Computacional */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Visão Computacional (Fotos)
              </span>
              <span className="rounded-md bg-sky-50 px-2 py-0.5 text-[11px] font-semibold text-sky-700 border border-sky-200">
                Multimodal
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-sky-700 tracking-tight">
              ${summary?.total_vision_cost_usd !== undefined ? summary.total_vision_cost_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2 flex justify-between">
            <span>Fotos: {summary?.total_vision_calls?.toLocaleString("pt-BR") ?? 0}</span>
            <span>Tokens: {summary?.total_vision_tokens?.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 4: Ingestão & Dados */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Ingestão & Dados (Crawler/Catálogo)
              </span>
              <span className="rounded-md bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-700 border border-teal-200">
                Backoffice
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-teal-700 tracking-tight">
              ${summary?.total_ingestion_cost_usd !== undefined ? summary.total_ingestion_cost_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2 flex justify-between">
            <span>Operações: {summary?.total_ingestion_calls?.toLocaleString("pt-BR") ?? 0}</span>
            <span>Tokens: {summary?.total_ingestion_tokens?.toLocaleString("pt-BR") ?? 0}</span>
          </p>
        </div>

        {/* Card 5: Custo Total */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo Total Geral (Infraestrutura)
              </span>
              <span className="rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700 border border-purple-200">
                USD
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-purple-700 tracking-tight">
              ${summary?.grand_total_cost_usd !== undefined
                ? summary.grand_total_cost_usd.toFixed(4)
                : ((summary?.total_cost_usd || 0) + (summary?.total_ingestion_cost_usd || 0)).toFixed(4)}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2 flex justify-between">
            <span>Atendimento: ${summary?.total_cost_usd?.toFixed(4) ?? "0.0000"}</span>
            <span>Ingestão: ${summary?.total_ingestion_cost_usd?.toFixed(4) ?? "0.0000"}</span>
          </p>
        </div>

        {/* Card 4: Custo Entrada */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo de Entrada (Prompt)
              </span>
              <span className="rounded-md bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700 border border-indigo-200">
                Contexto
              </span>
            </div>
            <p className="mt-3 text-2xl font-bold text-slate-900 tracking-tight">
              ${summary?.total_cost_prompt_usd !== undefined ? summary.total_cost_prompt_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2">
            Perguntas, sistema e RAG enviados
          </p>
        </div>

        {/* Card 5: Custo Saída */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo de Saída (Resposta)
              </span>
              <span className="rounded-md bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-200">
                Geração
              </span>
            </div>
            <p className="mt-3 text-2xl font-bold text-slate-900 tracking-tight">
              ${summary?.total_cost_completion_usd !== undefined ? summary.total_cost_completion_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2">
            Tokens de respostas gerados na nuvem
          </p>
        </div>

        {/* Card 6: Chats Encerrados */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Chats Encerrados
              </span>
              <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700 border border-slate-200">
                Sessões
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-slate-900 tracking-tight">
              {summary?.total_closed_chats ?? 0}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2">
            Finalizados manualmente ou inatividade
          </p>
        </div>
      </div>

      {/* Tabela de Detalhamento Diário */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-2xs overflow-hidden">
        <div className="border-b border-slate-200 bg-slate-50/70 px-6 py-4 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Detalhamento Diário dos Atendimentos Encerrados
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Agrupamento diário baseado na data de encerramento da conversa.
              {period === "custom" && ` (Filtrando dia ${formatarDataPtBr(selectedDate)})`}
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

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="border-b border-slate-200 bg-slate-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3">
                  Data
                </th>
                <th scope="col" className="px-5 py-3">
                  Chats Encerrados
                </th>
                <th scope="col" className="px-5 py-3">
                  Tokens Internos (Entrada / Saída)
                </th>
                <th scope="col" className="px-5 py-3">
                  Tokens Externos (Entrada / Saída)
                </th>
                <th scope="col" className="px-5 py-3">
                  Visão (Fotos / Custo)
                </th>
                <th scope="col" className="px-5 py-3">
                  Ingestão (Op / Custo)
                </th>
                <th scope="col" className="px-5 py-3">
                  Custo Entrada
                </th>
                <th scope="col" className="px-5 py-3">
                  Custo Saída
                </th>
                <th scope="col" className="px-5 py-3 text-right">
                  Custo Total
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
                daily.map((item) => (
                  <tr key={item.date} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-3.5 font-semibold text-slate-900">{item.date}</td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center justify-center rounded-full bg-slate-100 px-2.5 py-0.5 font-bold text-slate-800">
                        {item.closed_chats_count}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-medium text-slate-900">
                        {(item.internal_prompt_tokens + item.internal_completion_tokens).toLocaleString("pt-BR")}
                      </span>{" "}
                      <span className="text-slate-400 text-[11px]">
                        ({item.internal_prompt_tokens.toLocaleString("pt-BR")} /{" "}
                        {item.internal_completion_tokens.toLocaleString("pt-BR")})
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-medium text-slate-900">
                        {(item.external_prompt_tokens + item.external_completion_tokens).toLocaleString("pt-BR")}
                      </span>{" "}
                      <span className="text-slate-400 text-[11px]">
                        ({item.external_prompt_tokens.toLocaleString("pt-BR")} /{" "}
                        {item.external_completion_tokens.toLocaleString("pt-BR")})
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-semibold text-slate-900">
                        {item.vision_calls_count ?? 0} foto{(item.vision_calls_count ?? 0) === 1 ? "" : "s"}
                      </span>{" "}
                      <span className="text-slate-500 text-[11px] font-mono">
                        (${item.vision_cost_usd !== undefined ? item.vision_cost_usd.toFixed(4) : "0.0000"})
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-semibold text-slate-900">
                        {item.ingestion_calls_count ?? 0} op{(item.ingestion_calls_count ?? 0) === 1 ? "" : "s"}
                      </span>{" "}
                      <span className="text-slate-500 text-[11px] font-mono">
                        (${item.ingestion_cost_usd !== undefined ? item.ingestion_cost_usd.toFixed(4) : "0.0000"})
                      </span>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-600">
                      ${item.cost_prompt_usd.toFixed(4)}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-slate-600">
                      ${item.cost_completion_usd.toFixed(4)}
                    </td>
                    <td className="px-5 py-3.5 font-mono font-bold text-slate-900 text-right">
                      ${item.total_cost_usd.toFixed(4)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
