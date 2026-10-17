"use client";

type ToneProvider = "heuristica_llm" | "jev_openrouter";

interface RuntimeToneMonitorSectionProps {
  enabled: boolean;
  provider: ToneProvider;
  onEnabled: (v: boolean) => void;
  onProvider: (v: ToneProvider) => void;
}

export function RuntimeToneMonitorSection({
  enabled,
  provider,
  onEnabled,
  onProvider,
}: RuntimeToneMonitorSectionProps) {
  return (
    <div className="space-y-3 pt-4 border-t border-slate-200/80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>🛡️</span> Monitor de Tom &amp; Sentimento (R8)
        </h3>
        <span className="text-xs text-slate-500">Detecção de urgência e frustração do cliente</span>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs space-y-4">
        <div className="flex items-start gap-3 p-1">
          <input
            id="rt-tone-monitor-enabled"
            type="checkbox"
            checked={enabled}
            onChange={(e) => onEnabled(e.target.checked)}
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
              Analisa a carga emocional e tom do usuário a cada mensagem para permitir escalonamento
              inteligente para atendimento humano.
            </p>
          </div>
        </div>

        {enabled && (
          <div className="pt-3 border-t border-slate-100 space-y-2">
            <span className="block text-xs font-bold uppercase tracking-wider text-slate-500">
              Provedor de análise de tom
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(
                [
                  {
                    id: "rt-tone-monitor-provider-heuristica",
                    value: "heuristica_llm",
                    label: "Heurística + LLM Local (Ollama)",
                  },
                  {
                    id: "rt-tone-monitor-provider-jev",
                    value: "jev_openrouter",
                    label: "TypeSafe Jev (OpenRouter)",
                  },
                ] as { id: string; value: ToneProvider; label: string }[]
              ).map((opt) => (
                <label
                  key={opt.value}
                  htmlFor={opt.id}
                  className={`flex items-center gap-3 rounded-lg border p-3 transition-all cursor-pointer ${
                    provider === opt.value
                      ? "border-blue-400 bg-blue-50/30"
                      : "border-slate-200 bg-slate-50/50 hover:bg-white"
                  }`}
                >
                  <input
                    id={opt.id}
                    type="radio"
                    name="rt-tone-monitor-provider"
                    value={opt.value}
                    checked={provider === opt.value}
                    onChange={() => onProvider(opt.value)}
                    disabled={!enabled}
                    className="h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                  <span className="text-xs font-semibold text-slate-800">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
