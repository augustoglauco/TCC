import type { PlaygroundResultItem } from "@/lib/types/rag";

export function ComparisonResultCard({ item }: { item: PlaygroundResultItem }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h3 className="font-medium text-gray-900">{item.collection_name}</h3>

      {item.error ? (
        <p className="mt-2 rounded-md bg-red-50 px-3 py-2 text-sm text-red-800">{item.error}</p>
      ) : (
        <>
          {item.latency_ms !== undefined && item.latency_ms !== null && (
            <p className="mt-1 text-xs text-gray-500">{item.latency_ms.toFixed(0)} ms</p>
          )}
          {item.results && item.results.length > 0 ? (
            <ul className="mt-2 space-y-2">
              {item.results.map((resultado, indice) => (
                <li key={indice} className="rounded-md bg-gray-50 p-2 text-sm text-gray-700">
                  <p className="text-xs text-gray-500">
                    {resultado.source} — score {resultado.score.toFixed(3)}
                  </p>
                  <p>{resultado.content}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-gray-600">Nenhum resultado encontrado.</p>
          )}
        </>
      )}
    </div>
  );
}
