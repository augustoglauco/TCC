"use client";

import { useEffect, useState } from "react";

import { CrawlerApiError, runCrawler } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";
import type { CrawlRunResponse } from "@/lib/types/crawler";

export function CrawlerPanel({ onFinished }: { onFinished: () => void }) {
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState(1);
  const [maxPages, setMaxPages] = useState<number | "">("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<CrawlRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Só usado pra pré-preencher `maxPages` — falha ao carregar não impede o
    // form de funcionar (o backend usa seu próprio default se `max_pages`
    // não for enviado).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    getRuntimeSettings()
      .then((settings) => setMaxPages(settings.crawler_max_pages_default))
      .catch(() => {});
  }, []);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!url || isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setResult(null);

    try {
      const response = await runCrawler({
        url,
        depth,
        max_pages: maxPages === "" ? undefined : maxPages,
      });
      setResult(response);
      onFinished();
    } catch (err) {
      setError(err instanceof CrawlerApiError ? err.message : "Erro inesperado ao rodar o crawler.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
      <p className="text-gray-600">
        Navega a partir de uma URL semente (site próprio ou externo), seguindo links internos até a
        profundidade informada, e classifica cada página por domínio.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 space-y-6">
        <div>
          <label htmlFor="crawler-url" className="block text-sm font-medium text-gray-900">
            URL semente
          </label>
          <input
            id="crawler-url"
            type="url"
            required
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://exemplo.com"
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor="crawler-depth" className="block text-sm font-medium text-gray-900">
              Profundidade
            </label>
            <input
              id="crawler-depth"
              type="number"
              min={0}
              required
              value={depth}
              onChange={(event) => setDepth(Number(event.target.value))}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
          <div>
            <label htmlFor="crawler-max-pages" className="block text-sm font-medium text-gray-900">
              Máximo de páginas
            </label>
            <input
              id="crawler-max-pages"
              type="number"
              min={1}
              value={maxPages}
              onChange={(event) =>
                setMaxPages(event.target.value === "" ? "" : Number(event.target.value))
              }
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-gray-900"
            />
          </div>
        </div>

        <button
          type="submit"
          disabled={!url || isSubmitting}
          className="rounded-md bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {isSubmitting ? "Rodando..." : "Rodar crawler"}
        </button>
      </form>

      {result && (
        <p className="mt-6 rounded-md bg-green-50 px-4 py-3 text-green-800">
          {result.pages_visited} página(s) visitada(s) — {result.auto_ingested.length} ingerida(s)
          diretamente, {result.queued.length} na fila de revisão
          {result.errors.length > 0 ? `, ${result.errors.length} com erro` : ""}.
        </p>
      )}
      {error && <p className="mt-6 rounded-md bg-red-50 px-4 py-3 text-red-800">{error}</p>}
    </div>
  );
}
