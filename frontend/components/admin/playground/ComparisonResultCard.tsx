import type { PlaygroundResultItem } from "@/lib/types/rag";

function getScoreBadge(score: number) {
  if (score >= 0.8) {
    return {
      bg: "bg-emerald-50 text-emerald-700 border-emerald-200",
      bar: "bg-emerald-500",
      label: "Alta relevância",
    };
  }
  if (score >= 0.6) {
    return {
      bg: "bg-blue-50 text-blue-700 border-blue-200",
      bar: "bg-blue-500",
      label: "Boa relevância",
    };
  }
  return {
    bg: "bg-amber-50 text-amber-700 border-amber-200",
    bar: "bg-amber-500",
    label: "Relevância moderada",
  };
}

export function ComparisonResultCard({ item }: { item: PlaygroundResultItem }) {
  const resultCount = item.results?.length ?? 0;

  return (
    <div className="flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-xs transition-all hover:border-slate-300 hover:shadow-sm">
      {/* Header da Collection */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/80 px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-100/70 text-blue-700 text-xs font-bold">
            🗄️
          </span>
          <div>
            <h3 className="text-sm font-bold text-slate-900">{item.collection_name}</h3>
            <span className="text-[11px] text-slate-500">
              {item.error
                ? "Falha na consulta"
                : `${resultCount} chunk${resultCount === 1 ? "" : "s"} retornado${resultCount === 1 ? "" : "s"}`}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {item.latency_ms !== undefined && item.latency_ms !== null && (
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                item.latency_ms < 50
                  ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                  : item.latency_ms < 150
                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                  : "bg-amber-50 text-amber-700 border border-amber-200"
              }`}
              title="Tempo de resposta da collection"
            >
              <span className="text-[10px]">⚡</span>
              {item.latency_ms.toFixed(0)} ms
            </span>
          )}
        </div>
      </div>

      {/* Conteúdo dos Resultados */}
      <div className="flex-1 p-5">
        {item.error ? (
          <div className="rounded-xl border border-red-200 bg-red-50/60 p-4 text-sm text-red-800">
            <div className="flex items-start gap-2.5">
              <span className="text-base leading-none">⚠️</span>
              <div className="space-y-1">
                <p className="font-semibold">Erro ao consultar collection</p>
                <p className="text-xs text-red-700 leading-relaxed">{item.error}</p>
              </div>
            </div>
          </div>
        ) : (
          <>
            {item.results && item.results.length > 0 ? (
              <ul className="space-y-3.5">
                {item.results.map((resultado, indice) => {
                  const scoreConfig = getScoreBadge(resultado.score);
                  const scorePercentage = Math.min(
                    100,
                    Math.max(0, Math.round(resultado.score * 100)),
                  );

                  return (
                    <li
                      key={indice}
                      className="group rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 transition-all hover:border-slate-300 hover:bg-white hover:shadow-xs"
                    >
                      {/* Topo do Chunk: Arquivo de Origem e Score */}
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5 mb-2.5">
                        <div className="flex items-center gap-1.5 font-medium text-slate-800 text-xs">
                          <span className="text-slate-400">📄</span>
                          <span className="font-mono">{resultado.source}</span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-semibold ${scoreConfig.bg}`}
                          >
                            <span>score</span>
                            <span className="font-mono">{resultado.score.toFixed(3)}</span>
                          </span>
                        </div>
                      </div>

                      {/* Barra de Relevância */}
                      <div className="mb-2.5 flex items-center gap-2">
                        <div className="h-1.5 flex-1 rounded-full bg-slate-200/70 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${scoreConfig.bar}`}
                            style={{ width: `${scorePercentage}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-medium text-slate-400">
                          {scorePercentage}%
                        </span>
                      </div>

                      {/* Texto do Chunk */}
                      <p className="text-xs text-slate-700 leading-relaxed font-normal whitespace-pre-wrap">
                        {resultado.content}
                      </p>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 p-6 text-center">
                <span className="text-2xl">🔍</span>
                <p className="mt-2 text-sm font-medium text-slate-600">
                  Nenhum resultado encontrado.
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Esta collection não retornou chunks acima do limiar para o domínio selecionado.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
