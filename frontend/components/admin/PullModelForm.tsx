"use client";

import { useEffect, useRef, useState } from "react";

import { LocalModelsApiError, getPullStatus, pullModel } from "@/lib/api/localModels";
import type { PullStatusResponse } from "@/lib/types/localModels";

const POLL_INTERVAL_MS = 1000;

export interface PullModelFormProps {
  onPulled: () => void;
}

export function PullModelForm({ onPulled }: PullModelFormProps) {
  const [nome, setNome] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [progresso, setProgresso] = useState<PullStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function pararPolling() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  function iniciarPolling(nomeModelo: string) {
    intervalRef.current = setInterval(async () => {
      try {
        const status = await getPullStatus(nomeModelo);
        setProgresso(status);
        if (status.status === "done") {
          pararPolling();
          setEnviando(false);
          onPulled();
        } else if (status.status === "error") {
          pararPolling();
          setEnviando(false);
          setError(status.detail ?? "Erro ao baixar o modelo.");
        }
      } catch (err) {
        pararPolling();
        setEnviando(false);
        setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao consultar o progresso.");
      }
    }, POLL_INTERVAL_MS);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!nome.trim() || enviando) return;

    setEnviando(true);
    setError(null);
    setProgresso(null);

    try {
      await pullModel(nome);
      iniciarPolling(nome);
    } catch (err) {
      setEnviando(false);
      setError(err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao iniciar o download.");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="pull-model-name" className="block text-sm font-medium text-gray-900">
          Nome do modelo
        </label>
        <input
          id="pull-model-name"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="ex.: llama3.1:8b ou hf.co/usuario/repo"
          disabled={enviando}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <button
        type="submit"
        disabled={!nome.trim() || enviando}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {enviando ? "Baixando..." : "Baixar"}
      </button>

      {progresso && progresso.status === "pulling" && (
        <div className="text-sm text-gray-600">
          {progresso.percent !== null && (
            <div className="mt-1 h-2 w-full rounded-full bg-gray-200">
              <div
                className="h-2 rounded-full bg-gray-900"
                style={{ width: `${Math.min(100, Math.max(0, progresso.percent))}%` }}
              />
            </div>
          )}
          <p className="mt-1">
            {progresso.percent !== null ? `${progresso.percent.toFixed(0)}% — ` : ""}
            {progresso.detail}
          </p>
        </div>
      )}
      {progresso && progresso.status === "done" && (
        <p className="rounded-md bg-green-50 px-4 py-3 text-green-800">{progresso.detail ?? "Concluído."}</p>
      )}
      {error && <p className="rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </form>
  );
}
