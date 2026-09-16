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
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b border-gray-200 text-gray-500">
          <th className="py-2 pr-4">Nome</th>
          <th className="py-2 pr-4">Tamanho</th>
          <th className="py-2 pr-4">Baixado em</th>
          <th className="py-2 pr-4" />
        </tr>
      </thead>
      <tbody>
        {models.map((modelo) => (
          <tr key={modelo.name} className="border-b border-gray-100">
            <td className="py-2 pr-4 text-gray-900">
              {modelo.name}
              {modelo.is_active && (
                <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                  Ativo
                </span>
              )}
            </td>
            <td className="py-2 pr-4 text-gray-700">{formatarTamanho(modelo.size_bytes)}</td>
            <td className="py-2 pr-4 text-gray-500" title={modelo.modified_at}>
              {formatarDataRelativa(modelo.modified_at)}
            </td>
            <td className="py-2 pr-4 text-right">
              {!modelo.is_active && (
                <button
                  type="button"
                  onClick={() => handleAtivar(modelo)}
                  disabled={processando}
                  className="text-gray-700 hover:text-gray-900 disabled:opacity-50"
                >
                  Ativar
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
