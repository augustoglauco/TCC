"use client";

import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";

const VISION_PRESETS = [
  { tag: "google/gemma-4-31b-it:free", label: "Gemma 4 31B (Free)" },
  { tag: "google/gemini-flash-1.5", label: "Gemini Flash 1.5" },
  { tag: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
  { tag: "qwen/qwen-2.5-vl-72b-instruct:free", label: "Qwen 2.5 VL (Free)" },
];

type CaracteristicasModelo = NonNullable<ReturnType<typeof useModelCharacteristics>["data"]>;

function SeloGratuito() {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
      🎁 Gratuito (:free)
    </span>
  );
}

function PrecoModelo({ data, tag }: { data: CaracteristicasModelo; tag: string }) {
  const { pricing_prompt_per_1k: entrada, pricing_completion_per_1k: saida } = data;
  if (entrada !== null && saida !== null) {
    if (entrada === 0 && saida === 0) return <SeloGratuito />;
    return (
      <span>
        💰 Preço: <strong>${entrada.toFixed(5)}</strong>/1K in ·{" "}
        <strong>${saida.toFixed(5)}</strong>/1K out
      </span>
    );
  }
  if (tag.includes(":free")) return <SeloGratuito />;
  return <span className="text-slate-500">Preço dinâmico via OpenRouter</span>;
}

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
          📊 Preço &amp; Modalidades no OpenRouter
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
          {error.includes("404") ? "Sem catálogo público cacheado para este modelo." : error}
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
                  m === "image" ? "bg-purple-200 text-purple-900" : "bg-slate-200 text-slate-700"
                }`}
              >
                {m === "image" ? "🖼️ Imagem" : m === "text" ? "Texto" : m}
              </span>
            ))}
          </div>
          <div className="text-purple-950 font-mono">
            <PrecoModelo data={data} tag={trimmed} />
          </div>
        </div>
      )}
    </div>
  );
}

const inputCls =
  "block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20";

interface RuntimeVisionSectionProps {
  externalVisionModel: string;
  imageInternalConfidence: string;
  imageExternalConfidence: string;
  onVisionModel: (v: string) => void;
  onInternalConfidence: (v: string) => void;
  onExternalConfidence: (v: string) => void;
}

export function RuntimeVisionSection({
  externalVisionModel,
  imageInternalConfidence,
  imageExternalConfidence,
  onVisionModel,
  onInternalConfidence,
  onExternalConfidence,
}: RuntimeVisionSectionProps) {
  return (
    <div className="space-y-3 pt-4 border-t border-slate-200/80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>👁️</span> Visão Computacional &amp; Identificação por Foto (R6)
        </h3>
        <span className="text-xs text-slate-500">
          Limiares de confiança e modelo de visão para imagens
        </span>
      </div>

      <div className="space-y-4">
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
            onChange={(e) => onVisionModel(e.target.value)}
            placeholder="ex: google/gemini-flash-1.5"
            className={inputCls}
          />
          <p className="text-[11px] text-slate-500 leading-tight">
            Modelo multimodal para identificação externa por imagem. Vazio = desliga visão externa.
          </p>

          <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Sugestões:
            </span>
            {VISION_PRESETS.map((p) => (
              <button
                key={p.tag}
                type="button"
                onClick={() => onVisionModel(p.tag)}
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

          <VisionModelPreview tag={externalVisionModel} />
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label
                htmlFor="rt-image-internal-confidence"
                className="text-xs font-bold text-slate-800"
              >
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
              onChange={(e) => onInternalConfidence(e.target.value)}
              placeholder="0.30"
              className={inputCls}
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Score mínimo no CLIP vetorial do banco interno para aceitar diretamente a foto.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition-all">
            <div className="flex items-center justify-between">
              <label
                htmlFor="rt-image-external-confidence"
                className="text-xs font-bold text-slate-800"
              >
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
              onChange={(e) => onExternalConfidence(e.target.value)}
              placeholder="0.70"
              className={inputCls}
            />
            <p className="text-[11px] text-slate-500 leading-tight">
              Confiança mínima reportada pelo modelo multimodal para aceitar a identificação.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
