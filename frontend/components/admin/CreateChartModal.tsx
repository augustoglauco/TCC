"use client";

import React, { useState } from "react";
import type { AdminChartData } from "./DynamicChartCard";
import { createAdminChart } from "@/lib/api/charts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

interface CreateChartModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (chart: AdminChartData) => void;
}

interface DataRow {
  label: string;
  value: string;
}

export default function CreateChartModal({
  isOpen,
  onClose,
  onCreated,
}: CreateChartModalProps) {
  const token = useAuthStore((s) => s.token);

  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [tipoGrafico, setTipoGrafico] = useState("bar");
  const [formato, setFormato] = useState("number");
  const [fixado, setFixado] = useState(true);
  const [rows, setRows] = useState<DataRow[]>([
    { label: "", value: "" },
    { label: "", value: "" },
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAddRow = () => {
    setRows((prev) => [...prev, { label: "", value: "" }]);
  };

  const handleRemoveRow = (index: number) => {
    if (rows.length <= 1) return;
    setRows((prev) => prev.filter((_, i) => i !== index));
  };

  const handleRowChange = (index: number, field: "label" | "value", val: string) => {
    setRows((prev) => {
      const copy = [...prev];
      copy[index] = { ...copy[index], [field]: val };
      return copy;
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError("Você precisa estar autenticado como Administrador.");
      return;
    }

    if (!titulo.trim()) {
      setError("Por favor, preencha o título do gráfico.");
      return;
    }

    const validRows = rows.filter((r) => r.label.trim() !== "");
    if (validRows.length === 0) {
      setError("Adicione pelo menos um item com rótulo e valor.");
      return;
    }

    setLoading(true);
    setError(null);

    const dadosJson = validRows.map((r) => ({
      categoria: r.label.trim(),
      valor: parseFloat(r.value.replace(",", ".")) || 0,
    }));

    try {
      const newChart = await createAdminChart(
        {
          titulo: titulo.trim(),
          descricao: descricao.trim() || null,
          tipo_grafico: tipoGrafico,
          config_json: {
            x_key: "categoria",
            y_keys: ["valor"],
            format: formato,
          },
          dados_json: dadosJson,
          sql_query: "dynamic_user_data",
          fixado,
        },
        token,
      );

      onCreated(newChart);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Erro ao criar gráfico.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs">
      <div className="w-full max-w-xl rounded-2xl bg-white p-6 shadow-xl border border-slate-100 flex flex-col max-h-[90vh]">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <span className="text-xl">📊</span>
            <h2 className="text-lg font-bold text-slate-800">
              Criar Gráfico Personalizado
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors"
            aria-label="Fechar modal"
          >
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 pt-4 overflow-y-auto pr-1">
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="input-titulo" className="block text-xs font-semibold text-slate-700 mb-1">
              Título do Gráfico *
            </label>
            <input
              id="input-titulo"
              type="text"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              placeholder="Ex: Metas por Região Q3"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
              required
            />
          </div>

          <div>
            <label htmlFor="input-desc" className="block text-xs font-semibold text-slate-700 mb-1">
              Descrição
            </label>
            <input
              id="input-desc"
              type="text"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Ex: Comparativo das regiões no terceiro trimestre"
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="select-tipo" className="block text-xs font-semibold text-slate-700 mb-1">
                Tipo de Gráfico
              </label>
              <select
                id="select-tipo"
                value={tipoGrafico}
                onChange={(e) => setTipoGrafico(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
              >
                <option value="bar">Barras</option>
                <option value="line">Linhas</option>
                <option value="pie">Pizza</option>
                <option value="donut">Rosca (Donut)</option>
                <option value="area">Área</option>
              </select>
            </div>

            <div>
              <label htmlFor="select-formato" className="block text-xs font-semibold text-slate-700 mb-1">
                Formato dos Valores
              </label>
              <select
                id="select-formato"
                value={formato}
                onChange={(e) => setFormato(e.target.value)}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-hidden"
              >
                <option value="number">Numérico (123)</option>
                <option value="currency">Monetário (R$ 123,00)</option>
                <option value="percent">Percentual (12%)</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="check-fixado"
              type="checkbox"
              checked={fixado}
              onChange={(e) => setFixado(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="check-fixado" className="text-xs font-medium text-slate-700 cursor-pointer">
              Fixar este gráfico no topo do dashboard
            </label>
          </div>

          <div className="mt-1">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-700">
                Dados do Gráfico (Rótulos e Valores)
              </span>
              <button
                type="button"
                onClick={handleAddRow}
                className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline"
              >
                + Adicionar Linha
              </button>
            </div>

            <div className="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
              {rows.map((row, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={row.label}
                    onChange={(e) => handleRowChange(idx, "label", e.target.value)}
                    placeholder="Ex: Categoria"
                    className="flex-1 rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  />
                  <input
                    type="text"
                    value={row.value}
                    onChange={(e) => handleRowChange(idx, "value", e.target.value)}
                    placeholder="Ex: 100"
                    className="w-28 rounded-xl border border-slate-200 px-3 py-1.5 text-xs text-slate-800 focus:border-blue-500 focus:outline-hidden"
                  />
                  <button
                    type="button"
                    onClick={() => handleRemoveRow(idx)}
                    disabled={rows.length <= 1}
                    aria-label={`Remover linha ${idx + 1}`}
                    className="rounded-lg p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 disabled:opacity-30 transition-colors"
                  >
                    🗑️
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-4 border-t border-slate-100 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="rounded-xl bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? "Salvando..." : "Salvar Gráfico"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
