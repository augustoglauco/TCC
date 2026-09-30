"use client";

// Parâmetros de execução ajustáveis em runtime mantidos em memória no backend.
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
  const [routerProvider, setRouterProvider] = useState<
    "heuristica" | "heuristica_llm" | "jev_openrouter"
  >("heuristica_llm");
  const [toneMonitorEnabled, setToneMonitorEnabled] = useState(true);
  const [toneMonitorProvider, setToneMonitorProvider] = useState<
    "heuristica_llm" | "jev_openrouter"
  >("heuristica_llm");
  const [externalVisionModel, setExternalVisionModel] = useState("");
  const [imageInternalConfidence, setImageInternalConfidence] = useState("0.30");
  const [imageExternalConfidence, setImageExternalConfidence] = useState("0.70");
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
        setRouterProvider(atual.intent_router_provider ?? "heuristica_llm");
        setToneMonitorEnabled(atual.tone_monitor_enabled ?? true);
        setToneMonitorProvider(atual.tone_monitor_provider ?? "heuristica_llm");
        setExternalVisionModel(atual.external_vision_model_name ?? "");
        setImageInternalConfidence(
          atual.image_internal_confidence !== undefined && atual.image_internal_confidence !== null
            ? String(atual.image_internal_confidence)
            : "0.30",
        );
        setImageExternalConfidence(
          atual.image_external_confidence !== undefined && atual.image_external_confidence !== null
            ? String(atual.image_external_confidence)
            : "0.70",
        );
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
        local_llm_temperature: temperatura.trim() === "" ? null : Number(temperatura),
        local_llm_timeout_s: Number(localTimeout),
        external_llm_timeout_s: Number(externalTimeout),
        intent_router_provider: routerProvider,
        tone_monitor_enabled: toneMonitorEnabled,
        tone_monitor_provider: toneMonitorProvider,
        external_vision_model_name: externalVisionModel.trim() || undefined,
        image_internal_confidence:
          imageInternalConfidence.trim() === "" ? undefined : Number(imageInternalConfidence),
        image_external_confidence:
          imageExternalConfidence.trim() === "" ? undefined : Number(imageExternalConfidence),
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
    return (
      <div className="flex items-center justify-center py-12 text-slate-500">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
        <span className="ml-2.5 text-xs font-medium">Carregando parâmetros...</span>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-8">
      {/* Top Banner de Destaque das Configurações */}
      <div className="rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/80 via-blue-50/80 to-slate-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-600 text-white text-2xl shadow-sm">
            ⚙️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700">
                Parâmetros de Inferência & Orquestração
              </span>
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              Roteador:{" "}
              <span className="font-mono text-indigo-900">
                {routerProvider === "jev_openrouter"
                  ? "Jev OpenRouter"
                  : routerProvider === "heuristica"
                  ? "Heurística (Palavras-chave)"
                  : "Heurística + LLM Local"}
              </span>
            </h2>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-indigo-700 border border-indigo-200 shadow-2xs">
          <span>⚡ Configuração em Tempo de Execução</span>
        </div>
      </div>

      {/* Seção 1: Configurações de Inferência LLM */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🎛️</span> Parâmetros de Inferência LLM
          </h3>
          <span className="text-xs text-slate-500">Temperatura e limites de tempo de execução</span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Card Temperatura */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-temperature" className="text-xs font-bold text-slate-800">
                Temperatura do modelo local
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 2.0
              </span>
            </div>
            <input
              id="rt-temperature"
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperatura}
              onChange={(e) => setTemperatura(e.target.value)}
              placeholder="Default do modelo"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Vazio = usa a temperatura padrão definida pelo próprio modelo.
            </p>
          </div>

          {/* Card Timeout Local */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-local-timeout" className="text-xs font-bold text-slate-800">
                Timeout do modelo local
              </label>
              <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                segundos
              </span>
            </div>
            <input
              id="rt-local-timeout"
              type="number"
              min={0}
              max={300}
              step={1}
              value={localTimeout}
              onChange={(e) => setLocalTimeout(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Tempo limite máximo para respostas da API local do Ollama.
            </p>
          </div>

          {/* Card Timeout Externo */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-external-timeout" className="text-xs font-bold text-slate-800">
                Timeout do modelo externo
              </label>
              <span className="text-[10px] font-mono bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-bold">
                segundos
              </span>
            </div>
            <input
              id="rt-external-timeout"
              type="number"
              min={0}
              max={300}
              step={1}
              value={externalTimeout}
              onChange={(e) => setExternalTimeout(e.target.value)}
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Tempo limite máximo para requisições à API do OpenRouter.
            </p>
          </div>
        </div>
      </div>

      {/* Seção 2: Roteador de Intenções */}
      <div className="space-y-3 pt-4 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🧭</span> Roteador de Intenções & Classificação
          </h3>
          <span className="text-xs text-slate-500">Mecanismo de triagem e direcionamento</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* Opção 1: Heurística Pura */}
          <label
            htmlFor="rt-router-provider-heuristica"
            className={`flex flex-col justify-between rounded-xl border p-4 transition-all cursor-pointer ${
              routerProvider === "heuristica"
                ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                  LOCAL REGRAS
                </span>
                {routerProvider === "heuristica" && (
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    Selecionado
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-start gap-3">
                <input
                  id="rt-router-provider-heuristica"
                  type="radio"
                  name="rt-router-provider"
                  value="heuristica"
                  checked={routerProvider === "heuristica"}
                  onChange={() => setRouterProvider("heuristica")}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">
                    Heurística (Palavras-chave)
                  </h4>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                    Classificação determinística ultrarrápida (0 ms) baseada em palavras-chave. Se inconclusivo, escala direto para fora de escopo.
                  </p>
                </div>
              </div>
            </div>
          </label>

          {/* Opção 2: Heurística + LLM Local */}
          <label
            htmlFor="rt-router-provider-heuristica-llm"
            className={`flex flex-col justify-between rounded-xl border p-4 transition-all cursor-pointer ${
              routerProvider === "heuristica_llm"
                ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-700">
                  LOCAL HÍBRIDO
                </span>
                {routerProvider === "heuristica_llm" && (
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    Selecionado
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-start gap-3">
                <input
                  id="rt-router-provider-heuristica-llm"
                  type="radio"
                  name="rt-router-provider"
                  value="heuristica_llm"
                  checked={routerProvider === "heuristica_llm"}
                  onChange={() => setRouterProvider("heuristica_llm")}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">
                    Heurística + LLM Local (Ollama)
                  </h4>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                    Tenta palavras-chave primeiro; se for inconclusivo, consulta o modelo Ollama para classificar o domínio antes de desistir.
                  </p>
                </div>
              </div>
            </div>
          </label>

          {/* Opção 3: Jev OpenRouter */}
          <label
            htmlFor="rt-router-provider-jev"
            className={`flex flex-col justify-between rounded-xl border p-4 transition-all cursor-pointer ${
              routerProvider === "jev_openrouter"
                ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className="rounded bg-indigo-100 px-2 py-0.5 text-[10px] font-bold text-indigo-800">
                  OPENROUTER JEV
                </span>
                {routerProvider === "jev_openrouter" && (
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    Selecionado
                  </span>
                )}
              </div>

              <div className="mt-3 flex items-start gap-3">
                <input
                  id="rt-router-provider-jev"
                  type="radio"
                  name="rt-router-provider"
                  value="jev_openrouter"
                  checked={routerProvider === "jev_openrouter"}
                  onChange={() => setRouterProvider("jev_openrouter")}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">TypeSafe Jev (OpenRouter)</h4>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                    Classificação estritamente estruturada em JSON via endpoint /systemone de alta precisão e baixo custo.
                  </p>
                </div>
              </div>
            </div>
          </label>
        </div>
      </div>

      {/* Seção 3: Monitor de Tom (R8) */}
      <div className="space-y-3 pt-4 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🛡️</span> Monitor de Tom & Sentimento (R8)
          </h3>
          <span className="text-xs text-slate-500">
            Detecção de urgência e frustração do cliente
          </span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-4">
          <div className="flex items-start gap-3 p-1">
            <input
              id="rt-tone-monitor-enabled"
              type="checkbox"
              checked={toneMonitorEnabled}
              onChange={(e) => setToneMonitorEnabled(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
            />
            <div>
              <label
                htmlFor="rt-tone-monitor-enabled"
                className="text-sm font-bold text-slate-900 cursor-pointer"
              >
                Monitor de Tom ativo (R8)
              </label>
              <p className="mt-0.5 text-xs text-slate-500 leading-relaxed">
                Analisa a carga emocional e tom do usuário a cada mensagem para permitir
                escalonamento inteligente para atendimento humano.
              </p>
            </div>
          </div>

          {toneMonitorEnabled && (
            <div className="pt-3 border-t border-slate-100 space-y-2">
              <span className="block text-xs font-bold uppercase tracking-wider text-slate-500">
                Provedor de análise de tom
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <label
                  htmlFor="rt-tone-monitor-provider-heuristica"
                  className={`flex items-center gap-3 rounded-lg border p-3 transition-all cursor-pointer ${
                    toneMonitorProvider === "heuristica_llm"
                      ? "border-blue-400 bg-blue-50/30"
                      : "border-slate-200 bg-slate-50/50 hover:bg-white"
                  }`}
                >
                  <input
                    id="rt-tone-monitor-provider-heuristica"
                    type="radio"
                    name="rt-tone-monitor-provider"
                    value="heuristica_llm"
                    checked={toneMonitorProvider === "heuristica_llm"}
                    onChange={() => setToneMonitorProvider("heuristica_llm")}
                    disabled={!toneMonitorEnabled}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                  <span className="text-xs font-semibold text-slate-800">
                    Heurística + LLM Local (Ollama)
                  </span>
                </label>

                <label
                  htmlFor="rt-tone-monitor-provider-jev"
                  className={`flex items-center gap-3 rounded-lg border p-3 transition-all cursor-pointer ${
                    toneMonitorProvider === "jev_openrouter"
                      ? "border-blue-400 bg-blue-50/30"
                      : "border-slate-200 bg-slate-50/50 hover:bg-white"
                  }`}
                >
                  <input
                    id="rt-tone-monitor-provider-jev"
                    type="radio"
                    name="rt-tone-monitor-provider"
                    value="jev_openrouter"
                    checked={toneMonitorProvider === "jev_openrouter"}
                    onChange={() => setToneMonitorProvider("jev_openrouter")}
                    disabled={!toneMonitorEnabled}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                  <span className="text-xs font-semibold text-slate-800">
                    TypeSafe Jev (OpenRouter)
                  </span>
                </label>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Seção 4: Visão Computacional & Identificação por Imagem (R6) */}
      <div className="space-y-3 pt-4 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>👁️</span> Visão Computacional & Identificação por Foto (R6)
          </h3>
          <span className="text-xs text-slate-500">
            Limiares de confiança e modelo de visão para imagens
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Modelo de Visão Externo */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-external-vision-model" className="text-xs font-bold text-slate-800">
                Modelo de Visão (OpenRouter)
              </label>
              <span className="text-[10px] font-mono bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-bold">
                visão
              </span>
            </div>
            <input
              id="rt-external-vision-model"
              type="text"
              value={externalVisionModel}
              onChange={(e) => setExternalVisionModel(e.target.value)}
              placeholder="ex: google/gemini-flash-1.5"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Modelo multimodal para identificação externa por imagem. Vazio = desliga visão externa.
            </p>
          </div>

          {/* Confiança Catálogo Interno (CLIP) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-image-internal-confidence" className="text-xs font-bold text-slate-800">
                Limiar Catálogo Interno (CLIP)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 1.0
              </span>
            </div>
            <input
              id="rt-image-internal-confidence"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={imageInternalConfidence}
              onChange={(e) => setImageInternalConfidence(e.target.value)}
              placeholder="0.30"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Score mínimo no CLIP vetorial do banco interno para aceitar diretamente a foto.
            </p>
          </div>

          {/* Confiança Visão Externa */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-image-external-confidence" className="text-xs font-bold text-slate-800">
                Limiar Visão Externa
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 1.0
              </span>
            </div>
            <input
              id="rt-image-external-confidence"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={imageExternalConfidence}
              onChange={(e) => setImageExternalConfidence(e.target.value)}
              placeholder="0.70"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Confiança mínima reportada pelo modelo multimodal para aceitar a identificação.
            </p>
          </div>
        </div>
      </div>

      {/* Botão de Salvar */}
      <div className="flex justify-end pt-2">
        <button
          type="submit"
          disabled={salvando}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-7 py-3 text-xs sm:text-sm font-bold text-white shadow-sm transition-all hover:bg-slate-800 disabled:opacity-50 cursor-pointer"
        >
          {salvando ? "Aplicando..." : "Aplicar"}
        </button>
      </div>
    </form>
  );
}
