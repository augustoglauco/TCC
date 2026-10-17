"use client";

import { useEffect, useState } from "react";

import {
  RuntimeSettingsApiError,
  getRuntimeSettings,
  updateRuntimeSettings,
  preloadLocalModel,
  unloadLocalModel,
} from "@/lib/api/runtimeSettings";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { RuntimeSettings } from "@/lib/types/runtimeSettings";
import { RuntimeLlmParamsSection } from "./RuntimeLlmParamsSection";
import { RuntimeVramSection } from "./RuntimeVramSection";
import { RuntimeRouterSection } from "./RuntimeRouterSection";
import { RuntimeToneMonitorSection } from "./RuntimeToneMonitorSection";
import { RuntimeEstoqueSection } from "./RuntimeEstoqueSection";
import { RuntimeVisionSection } from "./RuntimeVisionSection";
import { RuntimeRagSection } from "./RuntimeRagSection";

export interface RuntimeSettingsFormProps {
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

function strOrEmpty(v: number | null | undefined): string {
  return v === null || v === undefined ? "" : String(v);
}

export function RuntimeSettingsForm({ onError, onSuccess }: RuntimeSettingsFormProps) {
  const token = useAuthStore((s) => s.token);
  const [settings, setSettings] = useState<RuntimeSettings | null>(null);
  const [temperatura, setTemperatura] = useState("");
  const [numCtx, setNumCtx] = useState("");
  const [topP, setTopP] = useState("");
  const [topK, setTopK] = useState("");
  const [repeatPenalty, setRepeatPenalty] = useState("");
  const [seed, setSeed] = useState("");
  const [localTimeout, setLocalTimeout] = useState("");
  const [externalTimeout, setExternalTimeout] = useState("");
  const [ragTopK, setRagTopK] = useState("3");
  const [ragScoreThreshold, setRagScoreThreshold] = useState("0.35");
  const [ragSearchDomainFallback, setRagSearchDomainFallback] = useState(true);
  const [routerProvider, setRouterProvider] = useState<
    "heuristica" | "heuristica_llm" | "jev_openrouter"
  >("heuristica_llm");
  const [toneMonitorEnabled, setToneMonitorEnabled] = useState(true);
  const [toneMonitorProvider, setToneMonitorProvider] = useState<
    "heuristica_llm" | "jev_openrouter"
  >("heuristica_llm");
  const [estoqueAgentMode, setEstoqueAgentMode] = useState<"desativado" | "deterministico" | "ia">(
    "deterministico",
  );
  const [estoqueAgentLlm, setEstoqueAgentLlm] = useState<"local" | "externo">("local");
  const [externalVisionModel, setExternalVisionModel] = useState("");
  const [imageInternalConfidence, setImageInternalConfidence] = useState("0.30");
  const [imageExternalConfidence, setImageExternalConfidence] = useState("0.70");
  const [keepAlive, setKeepAlive] = useState("-1");
  const [warmupOnStartup, setWarmupOnStartup] = useState(true);
  const [modelLoaded, setModelLoaded] = useState(false);
  const [vramBytes, setVramBytes] = useState<number | null>(null);
  const [acaoVramEmAndamento, setAcaoVramEmAndamento] = useState<"preload" | "unload" | null>(null);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    let cancelado = false;
    async function carregar() {
      if (!token) return;
      try {
        const atual = await getRuntimeSettings(token);
        if (cancelado) return;
        setSettings(atual);
        setTemperatura(strOrEmpty(atual.local_llm_temperature));
        setNumCtx(strOrEmpty(atual.local_llm_num_ctx));
        setTopP(strOrEmpty(atual.local_llm_top_p));
        setTopK(strOrEmpty(atual.local_llm_top_k));
        setRepeatPenalty(strOrEmpty(atual.local_llm_repeat_penalty));
        setSeed(strOrEmpty(atual.local_llm_seed));
        setLocalTimeout(String(atual.local_llm_timeout_s));
        setExternalTimeout(String(atual.external_llm_timeout_s));
        setRagTopK(atual.rag_top_k != null ? String(atual.rag_top_k) : "3");
        setRagScoreThreshold(
          atual.rag_score_threshold != null ? String(atual.rag_score_threshold) : "0.35",
        );
        setRagSearchDomainFallback(atual.rag_search_domain_fallback ?? true);
        setRouterProvider(atual.intent_router_provider ?? "heuristica_llm");
        setToneMonitorEnabled(atual.tone_monitor_enabled ?? true);
        setToneMonitorProvider(atual.tone_monitor_provider ?? "heuristica_llm");
        setEstoqueAgentMode(atual.estoque_agent_mode ?? "deterministico");
        setEstoqueAgentLlm(atual.estoque_agent_llm ?? "local");
        setExternalVisionModel(atual.external_vision_model_name ?? "");
        setImageInternalConfidence(
          atual.image_internal_confidence != null
            ? String(atual.image_internal_confidence)
            : "0.30",
        );
        setImageExternalConfidence(
          atual.image_external_confidence != null
            ? String(atual.image_external_confidence)
            : "0.70",
        );
        setKeepAlive(atual.local_llm_keep_alive ?? "-1");
        setWarmupOnStartup(atual.local_llm_warmup_on_startup ?? true);
        setModelLoaded(atual.local_model_loaded ?? false);
        setVramBytes(atual.local_model_vram_bytes ?? null);
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
  }, [token]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (salvando || !token) return;
    setSalvando(true);
    try {
      const atualizado = await updateRuntimeSettings(token, {
        local_llm_temperature: temperatura.trim() === "" ? null : Number(temperatura),
        local_llm_num_ctx: numCtx.trim() === "" ? null : Number(numCtx),
        local_llm_top_p: topP.trim() === "" ? null : Number(topP),
        local_llm_top_k: topK.trim() === "" ? null : Number(topK),
        local_llm_repeat_penalty: repeatPenalty.trim() === "" ? null : Number(repeatPenalty),
        local_llm_seed: seed.trim() === "" ? null : Number(seed),
        local_llm_timeout_s: Number(localTimeout),
        external_llm_timeout_s: Number(externalTimeout),
        rag_top_k: ragTopK.trim() === "" ? undefined : Number(ragTopK),
        rag_score_threshold:
          ragScoreThreshold.trim() === "" ? undefined : Number(ragScoreThreshold),
        rag_search_domain_fallback: ragSearchDomainFallback,
        intent_router_provider: routerProvider,
        tone_monitor_enabled: toneMonitorEnabled,
        tone_monitor_provider: toneMonitorProvider,
        estoque_agent_mode: estoqueAgentMode,
        estoque_agent_llm: estoqueAgentLlm,
        external_vision_model_name: externalVisionModel.trim() || undefined,
        image_internal_confidence:
          imageInternalConfidence.trim() === "" ? undefined : Number(imageInternalConfidence),
        image_external_confidence:
          imageExternalConfidence.trim() === "" ? undefined : Number(imageExternalConfidence),
        local_llm_keep_alive: keepAlive,
        local_llm_warmup_on_startup: warmupOnStartup,
      });
      setSettings(atualizado);
      setKeepAlive(atualizado.local_llm_keep_alive ?? "-1");
      setWarmupOnStartup(atualizado.local_llm_warmup_on_startup ?? true);
      setModelLoaded(atualizado.local_model_loaded ?? false);
      setVramBytes(atualizado.local_model_vram_bytes ?? null);
      onSuccess("Parâmetros de execução aplicados e salvos no banco.");
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

  async function handleCarregarVram() {
    if (acaoVramEmAndamento || !token) return;
    setAcaoVramEmAndamento("preload");
    try {
      const resp = await preloadLocalModel(token);
      setSettings(resp);
      setModelLoaded(resp.local_model_loaded ?? false);
      setVramBytes(resp.local_model_vram_bytes ?? null);
      onSuccess("Modelo local carregado na VRAM da GPU com sucesso!");
    } catch (err) {
      onError(
        err instanceof RuntimeSettingsApiError
          ? err.message
          : "Erro ao tentar carregar modelo na VRAM.",
      );
    } finally {
      setAcaoVramEmAndamento(null);
    }
  }

  async function handleLiberarVram() {
    if (acaoVramEmAndamento || !token) return;
    setAcaoVramEmAndamento("unload");
    try {
      const resp = await unloadLocalModel(token);
      setSettings(resp);
      setModelLoaded(resp.local_model_loaded ?? false);
      setVramBytes(resp.local_model_vram_bytes ?? null);
      onSuccess("VRAM liberada com sucesso (modelo descarregado).");
    } catch (err) {
      onError(
        err instanceof RuntimeSettingsApiError ? err.message : "Erro ao tentar liberar VRAM.",
      );
    } finally {
      setAcaoVramEmAndamento(null);
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
      {/* Banner */}
      <div className="rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/80 via-blue-50/80 to-slate-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-600 text-white text-2xl shadow-sm">
            ⚙️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700">
                Parâmetros de Inferência &amp; Orquestração
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

      <RuntimeLlmParamsSection
        temperatura={temperatura}
        numCtx={numCtx}
        topP={topP}
        topK={topK}
        repeatPenalty={repeatPenalty}
        seed={seed}
        localTimeout={localTimeout}
        externalTimeout={externalTimeout}
        onTemperatura={setTemperatura}
        onNumCtx={setNumCtx}
        onTopP={setTopP}
        onTopK={setTopK}
        onRepeatPenalty={setRepeatPenalty}
        onSeed={setSeed}
        onLocalTimeout={setLocalTimeout}
        onExternalTimeout={setExternalTimeout}
      />

      <RuntimeVramSection
        keepAlive={keepAlive}
        warmupOnStartup={warmupOnStartup}
        modelLoaded={modelLoaded}
        vramBytes={vramBytes}
        salvando={salvando}
        acaoVramEmAndamento={acaoVramEmAndamento}
        onKeepAlive={setKeepAlive}
        onWarmup={setWarmupOnStartup}
        onCarregar={handleCarregarVram}
        onLiberar={handleLiberarVram}
      />

      <RuntimeRouterSection routerProvider={routerProvider} onChange={setRouterProvider} />

      <RuntimeToneMonitorSection
        enabled={toneMonitorEnabled}
        provider={toneMonitorProvider}
        onEnabled={setToneMonitorEnabled}
        onProvider={setToneMonitorProvider}
      />

      <RuntimeEstoqueSection
        mode={estoqueAgentMode}
        llm={estoqueAgentLlm}
        onMode={setEstoqueAgentMode}
        onLlm={setEstoqueAgentLlm}
      />

      <RuntimeVisionSection
        externalVisionModel={externalVisionModel}
        imageInternalConfidence={imageInternalConfidence}
        imageExternalConfidence={imageExternalConfidence}
        onVisionModel={setExternalVisionModel}
        onInternalConfidence={setImageInternalConfidence}
        onExternalConfidence={setImageExternalConfidence}
      />

      <RuntimeRagSection
        ragTopK={ragTopK}
        ragScoreThreshold={ragScoreThreshold}
        ragSearchDomainFallback={ragSearchDomainFallback}
        onTopK={setRagTopK}
        onScoreThreshold={setRagScoreThreshold}
        onDomainFallback={setRagSearchDomainFallback}
      />

      <div className="rounded-xl border border-blue-200/80 bg-blue-50/60 p-4 shadow-2xs flex items-center justify-between gap-3 text-xs text-blue-900">
        <div className="flex items-center gap-2.5">
          <span className="text-base">💾</span>
          <div>
            <span className="font-bold block">Configurações Persistentes no Banco de Dados</span>
            <span className="text-blue-700 text-[11px]">
              Todos os parâmetros definidos nesta página são salvos no PostgreSQL e restaurados
              automaticamente ao reiniciar o backend.
            </span>
          </div>
        </div>
      </div>

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
