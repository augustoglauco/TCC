import type { PullStatusResponse } from "@/lib/types/localModels";

const SUGGESTIONS = ["llama3.1:8b", "mistral:7b", "phi3:mini", "gemma2:2b", "qwen2.5:7b"];

interface CampoNomeModeloProps {
  nome: string;
  enviando: boolean;
  onChange: (nome: string) => void;
}

export function CampoNomeModelo({ nome, enviando, onChange }: CampoNomeModeloProps) {
  return (
    <div>
      <label htmlFor="pull-model-name" className="block text-sm font-semibold text-slate-800">
        Nome do modelo
      </label>
      <div className="mt-1.5 flex gap-2">
        <input
          id="pull-model-name"
          value={nome}
          onChange={(e) => onChange(e.target.value)}
          placeholder="ex.: llama3.1:8b ou hf.co/usuario/repo"
          disabled={enviando}
          className="block flex-1 rounded-xl border border-slate-300 bg-slate-50/50 px-3.5 py-2.5 text-sm text-slate-900 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={!nome.trim() || enviando}
          className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition-all hover:bg-slate-800 disabled:opacity-50 shadow-2xs cursor-pointer shrink-0"
        >
          {enviando ? "Baixando..." : "Baixar"}
        </button>
      </div>

      {/* Sugestões rápidas em pílulas */}
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider">
          Sugestões rápidas:
        </span>
        {SUGGESTIONS.map((tag) => (
          <button
            key={tag}
            type="button"
            disabled={enviando}
            onClick={() => onChange(tag)}
            className="rounded-lg border border-slate-200 bg-slate-100/70 px-2 py-0.5 text-xs font-mono font-medium text-slate-700 transition-colors hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 disabled:opacity-50 cursor-pointer"
          >
            + {tag}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ProgressoPull({ progresso }: { progresso: PullStatusResponse }) {
  if (progresso.status === "done") {
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3.5 text-xs font-semibold text-emerald-800 flex items-center gap-1.5">
        <span>✅</span>
        <span>{progresso.detail ?? "Concluído."}</span>
      </div>
    );
  }
  if (progresso.status !== "pulling") return null;

  return (
    <div className="rounded-xl border border-blue-200/80 bg-blue-50/50 p-4 text-xs text-blue-900 space-y-2">
      <div className="flex justify-between font-semibold">
        <span>Baixando camadas do modelo...</span>
        <span>
          {progresso.percent !== null ? `${progresso.percent.toFixed(0)}%` : "Em progresso"}
        </span>
      </div>
      {progresso.percent !== null && (
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-blue-200/60">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${Math.min(100, Math.max(0, progresso.percent))}%` }}
          />
        </div>
      )}
      <p className="font-mono text-[11px] text-blue-700 truncate">{progresso.detail}</p>
    </div>
  );
}

export function ErroPull({ mensagem }: { mensagem: string }) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-3.5 text-xs font-semibold text-red-800 flex items-center gap-1.5">
      <span>⚠️</span>
      <span>{mensagem}</span>
    </div>
  );
}
