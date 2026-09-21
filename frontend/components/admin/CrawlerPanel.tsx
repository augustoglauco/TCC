"use client";

import { useEffect, useRef, useState } from "react";

import { runCrawlerStream } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";
import type { CrawlRunResponse } from "@/lib/types/crawler";

// Sem evento do backend por mais que este tempo (em segundos) enquanto o
// crawl ainda está "rodando" = provável travamento. O crawl real emite um
// evento "visitando" por página (heartbeat), então um silêncio longo é
// anômalo. `_FETCH_TIMEOUT_S` do backend é 10s por página; 20s dá margem.
const STALL_THRESHOLD_S = 20;

interface LiveProgress {
  currentUrl: string | null;
  visited: number;
  ingested: number;
  queued: number;
  errors: number;
}

const PROGRESSO_INICIAL: LiveProgress = {
  currentUrl: null,
  visited: 0,
  ingested: 0,
  queued: 0,
  errors: 0,
};

export function CrawlerPanel({ onFinished }: { onFinished: () => void }) {
  const [url, setUrl] = useState("");
  const [depth, setDepth] = useState(1);
  const [maxPages, setMaxPages] = useState<number | "">("");
  const [isRunning, setIsRunning] = useState(false);
  const [progress, setProgress] = useState<LiveProgress>(PROGRESSO_INICIAL);
  const [result, setResult] = useState<CrawlRunResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Heartbeat: instante (ms) do último evento recebido + "há quantos
  // segundos" derivado num tick de 1s. `lastActivityRef` é um ref (não
  // state) para o tick poder lê-lo sem recriar o intervalo a cada evento.
  const lastActivityRef = useRef<number>(0);
  const [secondsSinceActivity, setSecondsSinceActivity] = useState(0);

  useEffect(() => {
    // Só usado pra pré-preencher `maxPages` — falha ao carregar não impede o
    // form de funcionar (o backend usa seu próprio default se `max_pages`
    // não for enviado).
    getRuntimeSettings()
      .then((settings) => setMaxPages(settings.crawler_max_pages_default))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!isRunning) return;
    const id = setInterval(() => {
      setSecondsSinceActivity(Math.floor((Date.now() - lastActivityRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [isRunning]);

  function marcarAtividade() {
    lastActivityRef.current = Date.now();
    setSecondsSinceActivity(0);
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!url || isRunning) {
      return;
    }

    setIsRunning(true);
    setError(null);
    setResult(null);
    setProgress(PROGRESSO_INICIAL);
    marcarAtividade();

    await runCrawlerStream(
      { url, depth, max_pages: maxPages === "" ? undefined : maxPages },
      {
        onVisiting: (visitandoUrl) => {
          marcarAtividade();
          setProgress((atual) => ({
            ...atual,
            currentUrl: visitandoUrl,
            visited: atual.visited + 1,
          }));
        },
        onIngested: () => {
          marcarAtividade();
          setProgress((atual) => ({ ...atual, ingested: atual.ingested + 1 }));
        },
        onQueued: () => {
          marcarAtividade();
          setProgress((atual) => ({ ...atual, queued: atual.queued + 1 }));
        },
        onPageError: () => {
          marcarAtividade();
          setProgress((atual) => ({ ...atual, errors: atual.errors + 1 }));
        },
        onDone: (summary) => {
          setResult(summary);
          onFinished();
        },
        onError: (message) => {
          setError(message);
        },
      },
    );

    setIsRunning(false);
    setProgress((atual) => ({ ...atual, currentUrl: null }));
  }

  const stalled = isRunning && secondsSinceActivity >= STALL_THRESHOLD_S;

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
          disabled={!url || isRunning}
          className="rounded-md bg-gray-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {isRunning ? "Rodando..." : "Rodar crawler"}
        </button>
      </form>

      {isRunning && (
        <div
          data-testid="crawler-live-status"
          aria-live="polite"
          className="mt-6 rounded-md border border-blue-200 bg-blue-50 p-4"
        >
          <div className="flex items-center gap-2 text-sm font-semibold text-blue-800">
            <span
              className="inline-block h-2.5 w-2.5 animate-pulse rounded-full bg-blue-500"
              aria-hidden
            />
            {progress.currentUrl ? (
              <span className="break-all">
                Lendo: <span className="font-mono font-normal">{progress.currentUrl}</span>
              </span>
            ) : (
              <span>Iniciando o crawl…</span>
            )}
          </div>

          <dl className="mt-3 grid grid-cols-4 gap-2 text-center text-xs text-blue-900">
            <div>
              <dt className="text-blue-600">Visitadas</dt>
              <dd className="text-base font-bold">{progress.visited}</dd>
            </div>
            <div>
              <dt className="text-blue-600">Ingeridas</dt>
              <dd className="text-base font-bold">{progress.ingested}</dd>
            </div>
            <div>
              <dt className="text-blue-600">Fila</dt>
              <dd className="text-base font-bold">{progress.queued}</dd>
            </div>
            <div>
              <dt className="text-blue-600">Erros</dt>
              <dd className="text-base font-bold">{progress.errors}</dd>
            </div>
          </dl>

          <p className="mt-3 text-xs text-blue-700">
            Última atividade há {secondsSinceActivity}s
          </p>

          {stalled && (
            <p
              data-testid="crawler-stall-warning"
              role="alert"
              className="mt-2 rounded bg-amber-100 px-3 py-2 text-xs font-semibold text-amber-800"
            >
              ⚠️ Sem resposta do servidor há {secondsSinceActivity}s — o crawl pode ter travado.
            </p>
          )}
        </div>
      )}

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
