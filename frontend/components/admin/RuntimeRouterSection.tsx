"use client";

type RouterProvider = "heuristica" | "heuristica_llm" | "jev_openrouter";

interface RouterOption {
  id: string;
  value: RouterProvider;
  badge: string;
  badgeCls: string;
  title: string;
  description: string;
}

const OPTIONS: RouterOption[] = [
  {
    id: "rt-router-provider-heuristica",
    value: "heuristica",
    badge: "LOCAL REGRAS",
    badgeCls: "bg-slate-100 text-slate-600",
    title: "Heurística (Palavras-chave)",
    description:
      "Classificação determinística ultrarrápida (0 ms) baseada em palavras-chave. Se inconclusivo, escala direto para fora de escopo.",
  },
  {
    id: "rt-router-provider-heuristica-llm",
    value: "heuristica_llm",
    badge: "LOCAL HÍBRIDO",
    badgeCls: "bg-blue-100 text-blue-700",
    title: "Heurística + LLM Local (Ollama)",
    description:
      "Tenta palavras-chave primeiro; se for inconclusivo, consulta o modelo Ollama para classificar o domínio antes de desistir.",
  },
  {
    id: "rt-router-provider-jev",
    value: "jev_openrouter",
    badge: "OPENROUTER JEV",
    badgeCls: "bg-indigo-100 text-indigo-800",
    title: "TypeSafe Jev (OpenRouter)",
    description:
      "Classificação estritamente estruturada em JSON via endpoint /systemone de alta precisão e baixo custo.",
  },
];

interface RuntimeRouterSectionProps {
  routerProvider: RouterProvider;
  onChange: (v: RouterProvider) => void;
}

export function RuntimeRouterSection({ routerProvider, onChange }: RuntimeRouterSectionProps) {
  return (
    <div className="space-y-3 pt-4 border-t border-slate-200/80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>🧭</span> Roteador de Intenções &amp; Classificação
        </h3>
        <span className="text-xs text-slate-500">Mecanismo de triagem e direcionamento</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {OPTIONS.map((opt) => (
          <label
            key={opt.value}
            htmlFor={opt.id}
            className={`flex flex-col justify-between rounded-xl border p-4 transition-all cursor-pointer ${
              routerProvider === opt.value
                ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
            }`}
          >
            <div>
              <div className="flex items-center justify-between gap-2">
                <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${opt.badgeCls}`}>
                  {opt.badge}
                </span>
                {routerProvider === opt.value && (
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                    Selecionado
                  </span>
                )}
              </div>
              <div className="mt-3 flex items-start gap-3">
                <input
                  id={opt.id}
                  type="radio"
                  name="rt-router-provider"
                  value={opt.value}
                  checked={routerProvider === opt.value}
                  onChange={() => onChange(opt.value)}
                  className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <div>
                  <h4 className="font-bold text-slate-900 text-sm">{opt.title}</h4>
                  <p className="mt-1 text-xs text-slate-500 leading-relaxed">{opt.description}</p>
                </div>
              </div>
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
