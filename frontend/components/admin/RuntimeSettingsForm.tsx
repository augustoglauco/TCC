"use client";

// Parâmetros de execução ajustáveis em runtime mantidos em memória no backend.
import { useEffect, useState } from "react";

import {
  RuntimeSettingsApiError,
  getRuntimeSettings,
  updateRuntimeSettings,
  preloadLocalModel,
  unloadLocalModel,
} from "@/lib/api/runtimeSettings";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";
import type { RuntimeSettings } from "@/lib/types/runtimeSettings";

const VISION_PRESETS = [
  { tag: "google/gemma-4-31b-it:free", label: "Gemma 4 31B (Free)" },
  { tag: "google/gemini-flash-1.5", label: "Gemini Flash 1.5" },
  { tag: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
  { tag: "qwen/qwen-2.5-vl-72b-instruct:free", label: "Qwen 2.5 VL (Free)" },
];

function VisionModelPreview({ tag }: { tag: string }) {
  const trimmed = tag.trim();
  const { data, loading, error, refresh } = useModelCharacteristics("openrouter", trimmed);

  if (!trimmed) return null;

  return (
    <div
      data-testid="vision-model-preview"
      className="mt-2.5 rounded-lg border border-purple-200/80 bg-purple-50/50 p-2.5 text-xs space-y-1.5"
    >
      <div className="flex items-center justify-between">
        <span className="font-semibold text-purple-900 flex items-center gap-1 text-[11px]">
          📊 Preço & Modalidades no OpenRouter
        </span>
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          aria-label="Atualizar características da visão"
          title="Atualizar dados de preço do modelo de visão"
          className="text-purple-600 hover:text-purple-900 disabled:opacity-40 cursor-pointer text-xs"
        >
          {loading ? "⏳" : "⟳"}
        </button>
      </div>

      {loading && !data && (
        <div className="text-[11px] text-purple-700/70 italic">Carregando características...</div>
      )}

      {error && !data && (
        <div className="text-[11px] text-slate-500 italic">
          {error.includes("404")
            ? "Sem catálogo público cacheado para este modelo."
            : error}
        </div>
      )}

      {data && (
        <div className="space-y-1 text-[11px]">
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-slate-500 font-medium">Entrada:</span>
            {data.input_modalities.map((m) => (
              <span
                key={m}
                className={`rounded px-1.5 py-0.2 text-[10px] font-bold ${
                  m === "image"
                    ? "bg-purple-200 text-purple-900"
                    : "bg-slate-200 text-slate-700"
                }`}
              >
                {m === "image" ? "🖼️ Imagem" : m === "text" ? "Texto" : m}
              </span>
            ))}
          </div>

          <div className="text-purple-950 font-mono">
            {data.pricing_prompt_per_1k !== null && data.pricing_completion_per_1k !== null ? (
              data.pricing_prompt_per_1k === 0 && data.pricing_completion_per_1k === 0 ? (
                <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                  🎁 Gratuito (:free)
                </span>
              ) : (
                <span>
                  💰 Preço: <strong>${data.pricing_prompt_per_1k.toFixed(5)}</strong>/1K in ·{" "}
                  <strong>${data.pricing_completion_per_1k.toFixed(5)}</strong>/1K out
                </span>
              )
            ) : trimmed.includes(":free") ? (
              <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                🎁 Gratuito (:free)
              </span>
            ) : (
              <span className="text-slate-500">Preço dinâmico via OpenRouter</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function formatVram(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "0 GB";
  const gb = bytes / (1024 * 1024 * 1024);
  return `${gb.toFixed(2)} GB`;
}

export interface RuntimeSettingsFormProps {
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
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
        setTemperatura(
          atual.local_llm_temperature === null || atual.local_llm_temperature === undefined
            ? ""
            : String(atual.local_llm_temperature),
        );
        setNumCtx(
          atual.local_llm_num_ctx === null || atual.local_llm_num_ctx === undefined
            ? ""
            : String(atual.local_llm_num_ctx),
        );
        setTopP(
          atual.local_llm_top_p === null || atual.local_llm_top_p === undefined
            ? ""
            : String(atual.local_llm_top_p),
        );
        setTopK(
          atual.local_llm_top_k === null || atual.local_llm_top_k === undefined
            ? ""
            : String(atual.local_llm_top_k),
        );
        setRepeatPenalty(
          atual.local_llm_repeat_penalty === null || atual.local_llm_repeat_penalty === undefined
            ? ""
            : String(atual.local_llm_repeat_penalty),
        );
        setSeed(
          atual.local_llm_seed === null || atual.local_llm_seed === undefined
            ? ""
            : String(atual.local_llm_seed),
        );
        setLocalTimeout(String(atual.local_llm_timeout_s));
        setExternalTimeout(String(atual.external_llm_timeout_s));
        setRagTopK(
          atual.rag_top_k !== undefined && atual.rag_top_k !== null
            ? String(atual.rag_top_k)
            : "3",
        );
        setRagScoreThreshold(
          atual.rag_score_threshold !== undefined && atual.rag_score_threshold !== null
            ? String(atual.rag_score_threshold)
            : "0.35",
        );
        setRagSearchDomainFallback(atual.rag_search_domain_fallback ?? true);
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
        rag_score_threshold: ragScoreThreshold.trim() === "" ? undefined : Number(ragScoreThreshold),
        rag_search_domain_fallback: ragSearchDomainFallback,
        intent_router_provider: routerProvider,
        tone_monitor_enabled: toneMonitorEnabled,
        tone_monitor_provider: toneMonitorProvider,
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
        err instanceof RuntimeSettingsApiError
          ? err.message
          : "Erro ao tentar liberar VRAM.",
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
                Temperatura (temperature)
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
              Vazio = usa a temperatura padrão do modelo local (ex: 0.7).
            </p>
          </div>

          {/* Card Janela de Contexto (num_ctx) */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-num-ctx" className="text-xs font-bold text-slate-800">
                Janela de Contexto (num_ctx)
              </label>
              <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                tokens
              </span>
            </div>
            <input
              id="rt-num-ctx"
              type="number"
              min={256}
              max={131072}
              step={256}
              value={numCtx}
              onChange={(e) => setNumCtx(e.target.value)}
              placeholder="ex: 4096, 8192"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Tamanho do contexto enviado ao Ollama. Vazio = padrão (geralmente 2048).
            </p>
          </div>

          {/* Card Top-P */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-top-p" className="text-xs font-bold text-slate-800">
                Nucleus Sampling (top_p)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 1.0
              </span>
            </div>
            <input
              id="rt-top-p"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={topP}
              onChange={(e) => setTopP(e.target.value)}
              placeholder="ex: 0.9"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Corte cumulativo de probabilidade de tokens. Vazio = padrão (0.9).
            </p>
          </div>

          {/* Card Top-K */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-top-k" className="text-xs font-bold text-slate-800">
                Top-K Sampling (top_k)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                inteiro
              </span>
            </div>
            <input
              id="rt-top-k"
              type="number"
              min={1}
              max={200}
              step={1}
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              placeholder="ex: 40"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Limita o vocabulário aos K tokens mais prováveis. Vazio = padrão (40).
            </p>
          </div>

          {/* Card Repeat Penalty */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-repeat-penalty" className="text-xs font-bold text-slate-800">
                Penalidade Repetição (repeat_penalty)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 2.0
              </span>
            </div>
            <input
              id="rt-repeat-penalty"
              type="number"
              min={0}
              max={2}
              step={0.05}
              value={repeatPenalty}
              onChange={(e) => setRepeatPenalty(e.target.value)}
              placeholder="ex: 1.1"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Penaliza repetição de termos (&gt;1.0 reduz repetições). Vazio = padrão (1.1).
            </p>
          </div>

          {/* Card Seed */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-seed" className="text-xs font-bold text-slate-800">
                Semente Aleatória (seed)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                inteiro
              </span>
            </div>
            <input
              id="rt-seed"
              type="number"
              step={1}
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              placeholder="ex: 42"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Semente para determinismo em testes/estudos. Vazio = aleatório.
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

      {/* Seção: Otimização de Latência & Residência na VRAM */}
      <div className="space-y-4 pt-4 border-t border-slate-200/80">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>🚀</span> Residência na VRAM & Otimização de Latência (Ollama)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Evite latência de cold start mantendo os pesos do modelo local residentes na memória de GPU
            </p>
          </div>
          {/* Badge de Status VRAM */}
          <div className="flex items-center gap-2 self-start sm:self-auto">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border ${
                modelLoaded
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : "bg-slate-100 text-slate-600 border-slate-200"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  modelLoaded ? "bg-emerald-500 animate-pulse" : "bg-slate-400"
                }`}
              />
              {modelLoaded
                ? `Modelo Carregado na VRAM (${formatVram(vramBytes)})`
                : "Modelo Descarregado (0 GB)"}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Card Keep-Alive */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3 hover:border-slate-300 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <label htmlFor="rt-keep-alive" className="text-xs font-bold text-slate-800">
                  Tempo de Retenção na VRAM (keep_alive)
                </label>
                <span className="text-[10px] font-mono bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-bold">
                  Ollama
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Define por quanto tempo o modelo local permanece na memória GPU após responder.
              </p>
            </div>

            <div>
              <select
                id="rt-keep-alive"
                value={keepAlive}
                onChange={(e) => setKeepAlive(e.target.value)}
                className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-medium text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
              >
                <option value="-1">Permanente / Indefinido (-1) — Recomendado (Zero Latência)</option>
                <option value="24h">24 Horas (24h)</option>
                <option value="1h">1 Hora (1h)</option>
                <option value="30m">30 Minutos (30m)</option>
                <option value="15m">15 Minutos (15m)</option>
                <option value="5m">5 Minutos (5m — Padrão do Ollama)</option>
                <option value="0">Descarregar Imediatamente (0) — Economia Máxima de VRAM</option>
              </select>
            </div>

            <div className="text-[11px] text-slate-500 bg-slate-50 p-2.5 rounded-lg border border-slate-100 flex items-start gap-2">
              <span className="text-sm">💡</span>
              <span>
                Com <strong>Permanente (-1)</strong>, o modelo não é descarregado após 5 minutos de inatividade, eliminando a espera de recarga do modelo nas conversas.
              </span>
            </div>
          </div>

          {/* Card Warmup & Ações Manuais */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-3 hover:border-slate-300 transition-all flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800">
                  Pré-aquecimento (Warmup) & Controle Manual
                </span>
                <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                  Inicialização
                </span>
              </div>
              <p className="text-[11px] text-slate-500 mt-1">
                Suba o modelo para a GPU logo no boot do servidor ou faça a gestão manual sob demanda.
              </p>
            </div>

            <label className="flex items-start gap-2.5 cursor-pointer py-1">
              <input
                id="rt-warmup-startup"
                type="checkbox"
                checked={warmupOnStartup}
                onChange={(e) => setWarmupOnStartup(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
              />
              <div className="text-xs">
                <span className="font-semibold text-slate-800 block">
                  Pré-carregar modelo ao inicializar o backend
                </span>
                <span className="text-slate-500 text-[11px]">
                  Dispara uma carga não bloqueante na inicialização para o primeiro usuário ter resposta imediata.
                </span>
              </div>
            </label>

            <div className="pt-2 border-t border-slate-100 flex items-center gap-2">
              <button
                type="button"
                onClick={handleCarregarVram}
                disabled={salvando || acaoVramEmAndamento !== null}
                className="flex-1 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 disabled:opacity-50 cursor-pointer transition-colors"
              >
                {acaoVramEmAndamento === "preload" ? (
                  <>
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                    <span>Carregando...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>Carregar na GPU</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleLiberarVram}
                disabled={salvando || acaoVramEmAndamento !== null}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-100 border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 disabled:opacity-50 cursor-pointer transition-colors"
              >
                {acaoVramEmAndamento === "unload" ? (
                  <>
                    <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-700 border-t-transparent" />
                    <span>Liberando...</span>
                  </>
                ) : (
                  <>
                    <span>🧹</span>
                    <span>Liberar VRAM</span>
                  </>
                )}
              </button>
            </div>
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

        <div className="space-y-4">
          {/* Modelo de Visão Externo */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-external-vision-model" className="text-xs font-bold text-slate-800">
                Modelo de Visão (OpenRouter)
              </label>
              <span className="text-[10px] font-mono bg-purple-50 text-purple-700 px-1.5 py-0.5 rounded font-bold">
                multimodal
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

            {/* Sugestões Rápidas de Modelos de Visão */}
            <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Sugestões:
              </span>
              {VISION_PRESETS.map((p) => (
                <button
                  key={p.tag}
                  type="button"
                  onClick={() => setExternalVisionModel(p.tag)}
                  className={`rounded-md border px-2 py-0.5 text-[11px] font-mono transition-colors cursor-pointer ${
                    externalVisionModel === p.tag
                      ? "border-purple-400 bg-purple-100 text-purple-800 font-bold"
                      : "border-slate-200 bg-slate-100/70 text-slate-700 hover:bg-purple-50 hover:border-purple-200 hover:text-purple-700"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>

            {/* Preview de Características e Preço */}
            <VisionModelPreview tag={externalVisionModel} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
      </div>

      {/* Seção 5: Busca Vetorial & Recuperação RAG (Qdrant) */}
      <div className="space-y-3 pt-4 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>📚</span> Busca Vetorial & Recuperação RAG (Qdrant)
          </h3>
          <span className="text-xs text-slate-500">
            Parâmetros de recuperação vetorial e limiares do RAG
          </span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Card RAG Top-K */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-rag-top-k" className="text-xs font-bold text-slate-800">
                Quantidade Recuperada (rag_top_k)
              </label>
              <span className="text-[10px] font-mono bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded font-bold">
                trechos
              </span>
            </div>
            <input
              id="rt-rag-top-k"
              type="number"
              min={1}
              max={50}
              step={1}
              value={ragTopK}
              onChange={(e) => setRagTopK(e.target.value)}
              placeholder="3"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Número máximo de chunks relevantes retornados da base vetorial do Qdrant.
            </p>
          </div>

          {/* Card RAG Score Threshold */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-rag-score-threshold" className="text-xs font-bold text-slate-800">
                Limiar Similaridade (rag_score_threshold)
              </label>
              <span className="text-[10px] font-mono bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                0.0 – 1.0
              </span>
            </div>
            <input
              id="rt-rag-score-threshold"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={ragScoreThreshold}
              onChange={(e) => setRagScoreThreshold(e.target.value)}
              placeholder="0.35"
              className="block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Score mínimo de cosseno para aceitar o trecho na busca do Qdrant.
            </p>
          </div>

          {/* Card RAG Domain Fallback */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <label htmlFor="rt-rag-domain-fallback" className="text-xs font-bold text-slate-800">
                Fallback de Domínio
              </label>
              <span className="text-[10px] font-mono bg-indigo-50 text-indigo-700 px-1.5 py-0.5 rounded font-bold">
                Qdrant
              </span>
            </div>
            <label className="flex items-center gap-2.5 cursor-pointer py-1">
              <input
                id="rt-rag-domain-fallback"
                type="checkbox"
                checked={ragSearchDomainFallback}
                onChange={(e) => setRagSearchDomainFallback(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              />
              <span className="text-xs font-semibold text-slate-800">
                Fallback sem filtro de domínio
              </span>
            </label>
            <p className="text-[11px] text-slate-500 leading-tight">
              Se ativo, realiza segunda busca sem restrição de domínio caso nada seja encontrado.
            </p>
          </div>
        </div>
      </div>

      {/* Card Informativo de Persistência no Banco */}
      <div className="rounded-xl border border-blue-200/80 bg-blue-50/60 p-4 shadow-2xs flex items-center justify-between gap-3 text-xs text-blue-900">
        <div className="flex items-center gap-2.5">
          <span className="text-base">💾</span>
          <div>
            <span className="font-bold block">Configurações Persistentes no Banco de Dados</span>
            <span className="text-blue-700 text-[11px]">
              Todos os parâmetros definidos nesta página são salvos no PostgreSQL e restaurados automaticamente ao reiniciar o backend.
            </span>
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
