"use client";

// MVP: parâmetros de execução ajustáveis em runtime (além do MVP, a pedido
// explícito) — mesmo padrão de `LocalModelsTable`/`PullModelForm`: só em
// memória no processo do backend, sem persistência entre restarts. Ver
// docs/superpowers/specs/2026-09-16-local-model-manager-design.md e decisão
// registrada em docs/ARCHITECTURE.md §5.
import { useEffect, useState } from "react";

import { RuntimeSettingsApiError, getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";
import type { RuntimeSettings } from "@/lib/types/runtimeSettings";

export interface RuntimeSettingsFormProps {
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function RuntimeSettingsForm({ onError, onSuccess }: RuntimeSettingsFormProps) {
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [temperatura, setTemperatura] = useState("");
  const [localTimeout, setLocalTimeout] = useState("");
  const [externalTimeout, setExternalTimeout] = useState("");
  const [ragFallback, setRagFallback] = useState(false);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const atual = await getRuntimeSettings();
        if (cancelado) return;
        setSettings(atual);
        setTemperatura(atual.local_llm_temperature === null ? "" : String(atual.local_llm_temperature));
        setLocalTimeout(String(atual.local_llm_timeout_s));
        setExternalTimeout(String(atual.external_llm_timeout_s));
        setRagFallback(atual.rag_search_domain_fallback);
      } catch (err) {
        if (!cancelado) {
          onError(
            err instanceof RuntimeSettingsApiError
              ? err.message
              : "Erro inesperado ao carregar os parâmetros de execução.",
          );
        }
      }
    }

    carregar();
    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (salvando) return;

    setSalvando(true);
    try {
      const atualizado = await updateRuntimeSettings({
        // Campo vazio no input de temperatura = "usar o default do próprio
        // modelo" (manda `null` explícito, ver contrato do PUT).
        local_llm_temperature: temperatura.trim() === "" ? null : Number(temperatura),
        local_llm_timeout_s: Number(localTimeout),
        external_llm_timeout_s: Number(externalTimeout),
        rag_search_domain_fallback: ragFallback,
      });
      setSettings(atualizado);
      onSuccess("Parâmetros de execução aplicados.");
    } catch (err) {
      onError(
        err instanceof RuntimeSettingsApiError ? err.message : "Erro inesperado ao aplicar os parâmetros.",
      );
    } finally {
      setSalvando(false);
    }
  }

  if (settings === null) {
    return <p className="text-sm text-gray-600">Carregando...</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="rt-temperature" className="block text-sm font-medium text-gray-900">
          Temperatura do modelo local (0.0–2.0, vazio = default do modelo)
        </label>
        <input
          id="rt-temperature"
          type="number"
          min={0}
          max={2}
          step={0.1}
          value={temperatura}
          onChange={(e) => setTemperatura(e.target.value)}
          placeholder="default do modelo"
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
        <p className="mt-1 text-xs text-gray-500">
          Também afeta a classificação de intenção do roteador — valores baixos reduzem a
          variação entre chamadas idênticas.
        </p>
      </div>

      <div>
        <label htmlFor="rt-local-timeout" className="block text-sm font-medium text-gray-900">
          Timeout do modelo local (segundos)
        </label>
        <input
          id="rt-local-timeout"
          type="number"
          min={0}
          max={300}
          step={1}
          value={localTimeout}
          onChange={(e) => setLocalTimeout(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div>
        <label htmlFor="rt-external-timeout" className="block text-sm font-medium text-gray-900">
          Timeout do modelo externo (segundos)
        </label>
        <input
          id="rt-external-timeout"
          type="number"
          min={0}
          max={300}
          step={1}
          value={externalTimeout}
          onChange={(e) => setExternalTimeout(e.target.value)}
          className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
        />
      </div>

      <div className="flex items-center gap-2">
        <input
          id="rt-rag-fallback"
          type="checkbox"
          checked={ragFallback}
          onChange={(e) => setRagFallback(e.target.checked)}
          className="h-4 w-4 rounded border-gray-300"
        />
        <label htmlFor="rt-rag-fallback" className="text-sm font-medium text-gray-900">
          RAG: buscar sem filtro de domínio quando a busca filtrada vem vazia
        </label>
      </div>
      <p className="text-xs text-gray-500">
        Desligado por padrão — ligar sacrifica o isolamento entre domínios e o sinal de
        escalonamento do roteador (ver docs/ARCHITECTURE.md §5). Existe para comparação/experimento.
      </p>

      <button
        type="submit"
        disabled={salvando}
        className="rounded-md bg-gray-900 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {salvando ? "Aplicando..." : "Aplicar"}
      </button>
    </form>
  );
}
