"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  fetchTokenCostMetrics,
  TokenCostMetricsResponse,
  GetMetricsParams,
} from "@/lib/api/metrics";

export default function AdminMetricasPage() {
  const currentUser = useAuthStore((state) => state.user);
  const isCurrentAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const [period, setPeriod] = useState<"today" | "7d" | "30d" | "all">("7d");
  const [data, setData] = useState<TokenCostMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const carregarMetricas = useCallback(async (p: "today" | "7d" | "30d" | "all") => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchTokenCostMetrics({ period: p });
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar métricas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isCurrentAdmin) {
      void carregarMetricas(period);
    }
  }, [isCurrentAdmin, period, carregarMetricas]);

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
          <div className="flex items-center gap-2">
            <span className="text-2xl">📊</span>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              Métricas & Custos de IA
            </h1>
          </div>
          <p className="mt-1.5 text-xs sm:text-sm text-slate-600 max-w-3xl">
            Acompanhamento de consumo de tokens (locais vs externos), custos financeiros segregados
            (entrada/saída) e relatórios de atendimentos encerrados.
          </p>
        </div>

        {/* Filtros de Período */}
        <div className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white p-1 shadow-2xs self-start sm:self-auto">
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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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

        {/* Card 3: Custo Total */}
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Custo Total Acumulado
              </span>
              <span className="rounded-md bg-purple-50 px-2 py-0.5 text-[11px] font-semibold text-purple-700 border border-purple-200">
                USD
              </span>
            </div>
            <p className="mt-3 text-3xl font-extrabold text-purple-700 tracking-tight">
              ${summary?.total_cost_usd !== undefined ? summary.total_cost_usd.toFixed(4) : "0.0000"}
            </p>
          </div>
          <p className="mt-2 text-xs text-slate-500 border-t border-slate-100 pt-2">
            Entrada + Saída em modelos externos
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
            </p>
          </div>
          <button
            type="button"
            onClick={() => void carregarMetricas(period)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors shadow-2xs"
            disabled={loading}
          >
            <span className={loading ? "animate-spin" : ""}>🔄</span>
            <span>Atualizar</span>
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
                  <td colSpan={7} className="px-5 py-8 text-center text-slate-400">
                    {loading
                      ? "Carregando métricas..."
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
    </div>
  );
}
