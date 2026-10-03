"use client";

import { useState } from "react";

import { ComparisonResultCard } from "@/components/admin/playground/ComparisonResultCard";
import { PlaygroundForm } from "@/components/admin/playground/PlaygroundForm";
import { PlaygroundManualModal } from "@/components/admin/playground/PlaygroundManualModal";
import { RagApiError, runPlaygroundSearch } from "@/lib/api/rag";
import type { PlaygroundResultItem, RagCollection, RagDomain } from "@/lib/types/rag";

export function PlaygroundPanel({ collections }: { collections: RagCollection[] }) {
  const [resultados, setResultados] = useState<PlaygroundResultItem[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ultimaBusca, setUltimaBusca] = useState<{ query: string; domain: RagDomain } | null>(null);
  const [manualAberto, setManualAberto] = useState(false);

  async function handleSubmit(params: {
    query: string;
    domain: RagDomain;
    collectionIds: string[];
  }) {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await runPlaygroundSearch({
        query: params.query,
        domain: params.domain,
        collection_ids: params.collectionIds,
      });
      setResultados(response.items);
      setUltimaBusca({ query: params.query, domain: params.domain });
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao rodar a busca.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function limparResultados() {
    setResultados(null);
    setUltimaBusca(null);
    setError(null);
  }

  return (
    <div className="space-y-6">
      {/* Header com Contexto */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xs">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">🧪</span>
              <h2 className="text-lg font-bold text-slate-900">
                Playground de Busca Semântica
              </h2>
              <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 border border-blue-200/60">
                Qdrant RAG
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500 max-w-2xl leading-relaxed">
              Compare os resultados de busca da mesma pergunta em collections diferentes, avaliando chunks recuperados, scores de similaridade e tempo de resposta.
            </p>
          </div>

          <button
            type="button"
            onClick={() => setManualAberto(true)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-2xs transition-all hover:bg-slate-50 hover:border-slate-300 hover:text-slate-900 active:scale-[0.99] cursor-pointer"
          >
            <span>📖</span>
            <span>Como usar o Playground</span>
          </button>
        </div>

        {/* Formulário de Busca */}
        <div className="mt-6 border-t border-slate-100 pt-6">
          <PlaygroundForm
            collections={collections}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
          />
        </div>

        {/* Banner de Erro Geral */}
        {error && (
          <div className="mt-6 rounded-xl border border-red-200 bg-red-50/80 p-4 text-sm text-red-800">
            <div className="flex items-center gap-2.5">
              <span className="text-base">⚠️</span>
              <div>
                <p className="font-semibold text-xs text-red-900">Falha ao executar consulta comparativa</p>
                <p className="text-xs text-red-700 mt-0.5">{error}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Estado Vazio Inicial */}
      {!resultados && !isSubmitting && !error && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8">
          <div className="max-w-xl mx-auto text-center space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100/60 text-xl text-blue-700 shadow-2xs">
              ⚡
            </div>
            <h3 className="text-sm font-bold text-slate-800">
              Pronto para comparar o comportamento do RAG
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              Digite uma pergunta real de atendimento ou vendas, selecione o domínio correspondente e marque as collections que deseja confrontar.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-4 text-left">
              <div className="rounded-xl border border-slate-200/80 bg-white p-3 space-y-1">
                <span className="text-sm">🎯</span>
                <p className="text-xs font-semibold text-slate-800">Relevância Semântica</p>
                <p className="text-[11px] text-slate-500">Avalie os scores de cosseno dos chunks recuperados.</p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-white p-3 space-y-1">
                <span className="text-sm">⏱️</span>
                <p className="text-xs font-semibold text-slate-800">Latência Comparada</p>
                <p className="text-[11px] text-slate-500">Monitore o tempo de resposta k-NN em cada collection.</p>
              </div>
              <div className="rounded-xl border border-slate-200/80 bg-white p-3 space-y-1">
                <span className="text-sm">📑</span>
                <p className="text-xs font-semibold text-slate-800">Granularidade</p>
                <p className="text-[11px] text-slate-500">Analise o impacto do tamanho de chunk e overlap.</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Indicador de Carregamento */}
      {isSubmitting && (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-xs">
          <div className="inline-flex h-10 w-10 animate-spin items-center justify-center rounded-full border-3 border-blue-600 border-t-transparent mb-3" />
          <p className="text-sm font-semibold text-slate-800">
            Consultando collections no Qdrant...
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Gerando embeddings da pergunta e executando busca vetorial em paralelo.
          </p>
        </div>
      )}

      {/* Resultados da Busca */}
      {resultados && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 px-1">
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Resultados da Busca Comparativa
              </h3>
              {ultimaBusca && (
                <p className="text-xs text-slate-500 mt-0.5">
                  Pergunta: <span className="font-medium text-slate-700 italic">&ldquo;{ultimaBusca.query}&rdquo;</span> • Domínio: <span className="font-medium text-slate-700 uppercase">{ultimaBusca.domain}</span>
                </p>
              )}
            </div>

            <button
              type="button"
              onClick={limparResultados}
              className="text-xs font-semibold text-slate-500 hover:text-slate-800 underline transition-colors"
            >
              Limpar resultados
            </button>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {resultados.map((item) => (
              <ComparisonResultCard key={item.collection_id} item={item} />
            ))}
          </div>
        </div>
      )}

      <PlaygroundManualModal
        open={manualAberto}
        onOpenChange={setManualAberto}
      />
    </div>
  );
}
