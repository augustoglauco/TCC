"use client";

const inputCls =
  "block w-full rounded-lg border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm font-mono text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20";

interface RuntimeRagSectionProps {
  ragTopK: string;
  ragScoreThreshold: string;
  ragSearchDomainFallback: boolean;
  onTopK: (v: string) => void;
  onScoreThreshold: (v: string) => void;
  onDomainFallback: (v: boolean) => void;
}

export function RuntimeRagSection({
  ragTopK,
  ragScoreThreshold,
  ragSearchDomainFallback,
  onTopK,
  onScoreThreshold,
  onDomainFallback,
}: RuntimeRagSectionProps) {
  return (
    <div className="space-y-3 pt-4 border-t border-slate-200/80">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
          <span>📚</span> Busca Vetorial &amp; Recuperação RAG (Qdrant)
        </h3>
        <span className="text-xs text-slate-500">
          Parâmetros de recuperação vetorial e limiares do RAG
        </span>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
            onChange={(e) => onTopK(e.target.value)}
            placeholder="3"
            className={inputCls}
          />
          <p className="text-[11px] text-slate-500 leading-tight">
            Número máximo de chunks relevantes retornados da base vetorial do Qdrant.
          </p>
        </div>

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
            onChange={(e) => onScoreThreshold(e.target.value)}
            placeholder="0.35"
            className={inputCls}
          />
          <p className="text-[11px] text-slate-500 leading-tight">
            Score mínimo de cosseno para aceitar o trecho na busca do Qdrant.
          </p>
        </div>

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
              onChange={(e) => onDomainFallback(e.target.checked)}
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
  );
}
