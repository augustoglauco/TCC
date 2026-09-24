"use client";

// MVP: parâmetros de execução ajustáveis em runtime (além do MVP, a pedido
// explícito) — mesmo padrão de `LocalModelsTable`/`PullModelForm`: só em
// memória no processo do backend, sem persistência entre restarts. Ver
// docs/superpowers/specs/2026-09-16-local-model-manager-design.md e decisão
// registrada em docs/ARCHITECTURE.md §5.
import { useEffect, useState } from "react";

import {
  RuntimeSettingsApiError,
  getRuntimeSettings,
  updateRuntimeSettings,
} from "@/lib/api/runtimeSettings";
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
  const [routerProvider, setRouterProvider] = useState<"heuristica_llm" | "jev_openrouter">(
    "heuristica_llm",
  );
  const [toneMonitorEnabled, setToneMonitorEnabled] = useState(true);
  const [toneMonitorProvider, setToneMonitorProvider] = useState<
    "heuristica_llm" | "jev_openrouter"
  >("heuristica_llm");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let cancelado = false;

    async function carregar() {
      try {
        const atual = await getRuntimeSettings();
        if (cancelado) return;
        setSettings(atual);
        setTemperatura(
          atual.local_llm_temperature === null ? "" : String(atual.local_llm_temperature),
        );
        setLocalTimeout(String(atual.local_llm_timeout_s));
        setExternalTimeout(String(atual.external_llm_timeout_s));
        setRagFallback(atual.rag_search_domain_fallback);
        setRouterProvider(atual.intent_router_provider ?? "heuristica_llm");
        setToneMonitorEnabled(atual.tone_monitor_enabled ?? true);
        setToneMonitorProvider(atual.tone_monitor_provider ?? "heuristica_llm");
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
        intent_router_provider: routerProvider,
        tone_monitor_enabled: toneMonitorEnabled,
        tone_monitor_provider: toneMonitorProvider,
      });
      setSettings(atualizado);
      onSuccess("Parâmetros de execução aplicados.");
    } catch (err) {
      onError(
        err instanceof RuntimeSettingsApiError
          ? err.message
          : "Erro inesperado ao aplicar os parâmetros.",
      );
    } finally {
      setSalvando(false);
    }
  }

  if (settings === null) {
    return <p className="text-sm text-gray-600">Carregando...</p>;
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Seção 1: Inferencia LLM */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 sm:p-5 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3">
          <span className="text-base">🎛️</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Configurações de Inferência LLM</h3>
            <p className="text-xs text-slate-500">Temperatura e orçamentos de timeout de execução</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="space-y-1">
            <label htmlFor="rt-temperature" className="block text-xs font-semibold text-slate-800">
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
              placeholder="Default do modelo"
              className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500">Vazio = usa o padrão do modelo</p>
          </div>

          <div className="space-y-1">
            <label htmlFor="rt-local-timeout" className="block text-xs font-semibold text-slate-800">
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
              className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500">Limite Ollama</p>
          </div>

          <div className="space-y-1">
            <label htmlFor="rt-external-timeout" className="block text-xs font-semibold text-slate-800">
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
              className="block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500">Limite OpenRouter API</p>
          </div>
        </div>
      </div>

      {/* Seção 2: Roteador de Intenções */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 sm:p-5 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3">
          <span className="text-base">🧭</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Roteador de Intenções & Classificação</h3>
            <p className="text-xs text-slate-500">Selecione o mecanismo de triagem e direcionamento de mensagens</p>
          </div>
        </div>

        <div>
          <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">
            Provedor de classificação de intenção
          </span>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label
              htmlFor="rt-router-provider-heuristica"
              className={`flex items-start gap-3 rounded-xl border p-3.5 transition-all cursor-pointer ${
                routerProvider === "heuristica_llm"
                  ? "border-blue-500 bg-blue-50/60 ring-1 ring-blue-500"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <input
                id="rt-router-provider-heuristica"
                type="radio"
                name="rt-router-provider"
                value="heuristica_llm"
                checked={routerProvider === "heuristica_llm"}
                onChange={() => setRouterProvider("heuristica_llm")}
                className="mt-0.5 h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="space-y-0.5">
                <span className="block text-xs font-semibold text-slate-900">
                  Heurística + LLM Local (Ollama)
                </span>
                <span className="block text-[11px] text-slate-500 leading-relaxed">
                  Padrão: Palavras-chave locais com fallback para o modelo Ollama local.
                </span>
              </div>
            </label>

            <label
              htmlFor="rt-router-provider-jev"
              className={`flex items-start gap-3 rounded-xl border p-3.5 transition-all cursor-pointer ${
                routerProvider === "jev_openrouter"
                  ? "border-blue-500 bg-blue-50/60 ring-1 ring-blue-500"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <input
                id="rt-router-provider-jev"
                type="radio"
                name="rt-router-provider"
                value="jev_openrouter"
                checked={routerProvider === "jev_openrouter"}
                onChange={() => setRouterProvider("jev_openrouter")}
                className="mt-0.5 h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <div className="space-y-0.5">
                <span className="block text-xs font-semibold text-slate-900">
                  TypeSafe Jev (OpenRouter)
                </span>
                <span className="block text-[11px] text-slate-500 leading-relaxed">
                  Classificação estruturada via endpoint /systemone de alta velocidade.
                </span>
              </div>
            </label>
          </div>
        </div>
      </div>

      {/* Seção 3: Monitor de Tom */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-4 sm:p-5 space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-200/80 pb-3">
          <span className="text-base">🛡️</span>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Monitor de Tom (R8)</h3>
            <p className="text-xs text-slate-500">Monitoramento em tempo real de urgência e insatisfação do cliente</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-white p-3.5">
            <input
              id="rt-tone-monitor-enabled"
              type="checkbox"
              checked={toneMonitorEnabled}
              onChange={(e) => setToneMonitorEnabled(e.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <div className="space-y-0.5">
              <label htmlFor="rt-tone-monitor-enabled" className="text-xs font-semibold text-slate-900 cursor-pointer">
                Monitor de Tom ativo (R8)
              </label>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Monitora sinais de insatisfação/urgência nas mensagens para transição e escalonamento humano.
              </p>
            </div>
          </div>

          <div className="pl-2 border-l-2 border-slate-200 ml-2 space-y-2">
            <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Provedor do Monitor de Tom (fallback ambíguo)
            </span>
            <div className="flex flex-wrap gap-4">
              <label htmlFor="rt-tone-monitor-provider-heuristica" className="flex items-center gap-2 text-xs font-medium text-slate-800 cursor-pointer">
                <input
                  id="rt-tone-monitor-provider-heuristica"
                  type="radio"
                  name="rt-tone-monitor-provider"
                  value="heuristica_llm"
                  checked={toneMonitorProvider === "heuristica_llm"}
                  onChange={() => setToneMonitorProvider("heuristica_llm")}
                  disabled={!toneMonitorEnabled}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 disabled:opacity-40"
                />
                Heurística + LLM Local (Ollama)
              </label>

              <label htmlFor="rt-tone-monitor-provider-jev" className="flex items-center gap-2 text-xs font-medium text-slate-800 cursor-pointer">
                <input
                  id="rt-tone-monitor-provider-jev"
                  type="radio"
                  name="rt-tone-monitor-provider"
                  value="jev_openrouter"
                  checked={toneMonitorProvider === "jev_openrouter"}
                  onChange={() => setToneMonitorProvider("jev_openrouter")}
                  disabled={!toneMonitorEnabled}
                  className="h-4 w-4 text-blue-600 focus:ring-blue-500 disabled:opacity-40"
                />
                TypeSafe Jev (OpenRouter)
              </label>
            </div>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          type="submit"
          disabled={salvando}
          className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-6 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-md transition-all hover:bg-slate-800 hover:shadow-lg disabled:opacity-50 cursor-pointer"
        >
          {salvando ? "Aplicando..." : "Aplicar"}
        </button>
      </div>
    </form>
  );
}
