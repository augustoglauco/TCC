"use client";

import { useState } from "react";

import { ComparisonResultCard } from "@/components/admin/playground/ComparisonResultCard";
import { PlaygroundForm } from "@/components/admin/playground/PlaygroundForm";
import { RagApiError, runPlaygroundSearch } from "@/lib/api/rag";
import type { PlaygroundResultItem, RagCollection, RagDomain } from "@/lib/types/rag";

export function PlaygroundPanel({ collections }: { collections: RagCollection[] }) {
  const [resultados, setResultados] = useState<PlaygroundResultItem[] | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(params: { query: string; domain: RagDomain; collectionIds: string[] }) {
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await runPlaygroundSearch({
        query: params.query,
        domain: params.domain,
        collection_ids: params.collectionIds,
      });
      setResultados(response.items);
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao rodar a busca.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Compare os resultados de busca da mesma pergunta em collections diferentes.
      </p>

      <div className="mt-6">
        <PlaygroundForm collections={collections} onSubmit={handleSubmit} isSubmitting={isSubmitting} />
      </div>

      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}

      {resultados && (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
          {resultados.map((item) => (
            <ComparisonResultCard key={item.collection_id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
