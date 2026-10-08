"use client";

import React, { useState } from "react";
import ChartRenderer from "@/components/charts/ChartRenderer";

export interface AdminChartData {
  id: string;
  titulo: string;
  descricao?: string | null;
  tipo_grafico: string;
  config_json: Record<string, any>;
  dados_json: Array<Record<string, any>>;
  sql_query?: string | null;
  fixado: boolean;
  ordem: number;
  criado_em?: string;
  atualizado_em?: string;
}

interface DynamicChartCardProps {
  chart: AdminChartData;
  onRefresh: (id: string) => void | Promise<void>;
  onTogglePin: (id: string, fixado: boolean) => void | Promise<void>;
  onDelete: (id: string) => void | Promise<void>;
  onEditTitle?: (id: string, novoTitulo: string) => void | Promise<void>;
}

const TIPO_LABELS: Record<string, string> = {
  bar: "Barras",
  line: "Linhas",
  pie: "Pizza",
  area: "Área",
  donut: "Donut",
};

export default function DynamicChartCard({
  chart,
  onRefresh,
  onTogglePin,
  onDelete,
  onEditTitle,
}: DynamicChartCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [titleValue, setTitleValue] = useState(chart.titulo);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showSqlBubble, setShowSqlBubble] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await onRefresh(chart.id);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSaveTitle = async () => {
    if (titleValue.trim() && titleValue !== chart.titulo && onEditTitle) {
      await onEditTitle(chart.id, titleValue.trim());
    }
    setIsEditing(false);
  };

  const formatUpdatedAt = (dateStr?: string) => {
    if (!dateStr) return "";
    try {
      const d = new Date(dateStr);
      return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs transition-all hover:shadow-md">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 border-b border-slate-100 bg-slate-50/50 p-4">
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                value={titleValue}
                onChange={(e) => setTitleValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSaveTitle()}
                className="w-full rounded-md border border-blue-400 px-2 py-1 text-sm font-semibold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                autoFocus
              />
              <button
                type="button"
                onClick={handleSaveTitle}
                className="rounded-md bg-blue-600 px-2 py-1 text-xs font-semibold text-white hover:bg-blue-700"
              >
                Salvar
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <h3
                className="truncate text-base font-bold text-slate-800"
                title={chart.titulo}
              >
                {chart.titulo}
              </h3>
              {onEditTitle && (
                <button
                  type="button"
                  onClick={() => setIsEditing(true)}
                  title="Editar título"
                  className="text-slate-400 hover:text-slate-600"
                >
                  ✏️
                </button>
              )}
            </div>
          )}
          {chart.descricao && (
            <p className="mt-0.5 truncate text-xs text-slate-500" title={chart.descricao}>
              {chart.descricao}
            </p>
          )}
        </div>

        {/* Action icons */}
        <div className="flex items-center gap-1 shrink-0">
          <span className="mr-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
            {TIPO_LABELS[chart.tipo_grafico] || chart.tipo_grafico}
          </span>

          <button
            type="button"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Atualizar dados"
            className={`rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors ${
              isRefreshing ? "animate-spin text-blue-600" : ""
            }`}
          >
            🔄
          </button>

          <button
            type="button"
            onClick={() => onTogglePin(chart.id, !chart.fixado)}
            title={chart.fixado ? "Desafixar" : "Fixar no topo"}
            className={`rounded-lg p-1.5 transition-colors ${
              chart.fixado
                ? "bg-amber-50 text-amber-600 hover:bg-amber-100"
                : "text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            }`}
          >
            📌
          </button>

          <button
            type="button"
            onClick={() => onDelete(chart.id)}
            title="Excluir gráfico"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            🗑️
          </button>
        </div>
      </div>

      {/* Chart Canvas */}
      <div className="p-4 flex-1">
        <ChartRenderer
          tipo_grafico={chart.tipo_grafico}
          config={chart.config_json}
          dados={chart.dados_json}
          height={260}
        />
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between border-t border-slate-100 bg-slate-50/30 px-4 py-2 text-[11px] text-slate-400">
        <span>
          {chart.atualizado_em ? `Atualizado às ${formatUpdatedAt(chart.atualizado_em)}` : "Recente"}
        </span>
        {chart.sql_query && (
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowSqlBubble((prev) => !prev)}
              title="Exibir SQL Dinâmico"
              className="flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-200 hover:text-slate-800 transition-colors cursor-pointer"
            >
              <span>SQL Dinâmico</span>
              <span className="text-xs">⚙️</span>
            </button>

            {showSqlBubble && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowSqlBubble(false)}
                />
                <div className="absolute right-0 bottom-full mb-2 z-20 w-72 sm:w-96 max-w-[calc(100vw-2rem)] rounded-xl border border-slate-700 bg-slate-900 p-3 text-slate-100 shadow-xl text-xs font-mono">
                  <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-800 font-sans font-semibold text-slate-300">
                    <span>SQL Dinâmico</span>
                    <button
                      type="button"
                      onClick={() => setShowSqlBubble(false)}
                      className="text-slate-400 hover:text-slate-200"
                      title="Fechar"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="max-h-48 overflow-y-auto whitespace-pre-wrap break-words leading-relaxed text-slate-200">
                    {chart.sql_query}
                  </div>
                  <div className="absolute -bottom-1.5 right-4 h-3 w-3 rotate-45 border-b border-r border-slate-700 bg-slate-900" />
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
