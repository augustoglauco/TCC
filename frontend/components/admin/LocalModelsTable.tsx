"use client";

import { useState } from "react";

import { LocalModelsApiError, activateModel } from "@/lib/api/localModels";
import type { LocalModel } from "@/lib/types/localModels";

function formatarTamanho(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  return `${gb.toFixed(1)} GB`;
}

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDias <= 0) return "hoje";
  if (diffDias === 1) return "há 1 dia";
  return `há ${diffDias} dias`;
}

export interface LocalModelsTableProps {
  models: LocalModel[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function LocalModelsTable({ models, onChanged, onError, onSuccess }: LocalModelsTableProps) {
  const [processando, setProcessando] = useState(false);

  async function handleAtivar(modelo: LocalModel) {
    setProcessando(true);
    try {
      await activateModel(modelo.name);
      onSuccess(`"${modelo.name}" agora é o modelo ativo no chat.`);
      onChanged();
    } catch (err) {
      onError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao ativar o modelo.");
    } finally {
      setProcessando(false);
    }
  }

  if (models.length === 0) {
    return <p className="text-sm text-gray-600">Nenhum modelo local baixado ainda.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
            <th className="py-3 px-4">Nome</th>
            <th className="py-3 px-4">Tamanho</th>
            <th className="py-3 px-4">Baixado em</th>
            <th className="py-3 px-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {models.map((modelo) => (
            <tr key={modelo.name} className="transition-colors hover:bg-slate-50/60">
              <td className="py-3.5 px-4 font-semibold text-slate-900">
                <div className="inline-flex items-center gap-2">
                  <span>{modelo.name}</span>
                  {modelo.is_active && (
                    <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200/80 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 shadow-2xs">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      Ativo
                    </span>
                  )}
                </div>
              </td>
              <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">{formatarTamanho(modelo.size_bytes)}</td>
              <td className="py-3.5 px-4 text-slate-500 text-xs" title={modelo.modified_at}>
                {formatarDataRelativa(modelo.modified_at)}
              </td>
              <td className="py-3.5 px-4 text-right whitespace-nowrap">
                {!modelo.is_active && (
                  <button
                    type="button"
                    onClick={() => handleAtivar(modelo)}
                    disabled={processando}
                    className="inline-flex items-center gap-1 rounded-lg border border-indigo-200/80 bg-indigo-50/50 px-2.5 py-1 text-xs font-semibold text-indigo-700 shadow-2xs transition-colors hover:bg-indigo-100/80 hover:text-indigo-800 disabled:opacity-50"
                  >
                    Ativar
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
