import { getPurposeLabel } from "@/lib/hooks/useCollectionsTable";
import type { RagCollection } from "@/lib/types/rag";

const BADGE_BASE =
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold shadow-2xs";

const BADGE_PURPOSE: Record<string, string> = {
  mcp_b2b: "border-purple-200/80 bg-purple-50 text-purple-700",
  admin: "border-rose-200/80 bg-rose-50 text-rose-700",
  chat: "border-slate-200/80 bg-slate-50 text-slate-600",
};

function PurposeBadge({ purpose }: { purpose?: string }) {
  const estilo = BADGE_PURPOSE[purpose ?? ""] ?? BADGE_PURPOSE.chat;
  return <span className={`${BADGE_BASE} ${estilo}`}>{getPurposeLabel(purpose)}</span>;
}

function NomeCell({ collection }: { collection: RagCollection }) {
  return (
    <td className="py-2.5 px-3 font-semibold text-slate-900">
      <div className="inline-flex items-center gap-2">
        <span className="truncate max-w-[160px]" title={collection.name}>
          {collection.name}
        </span>
        {collection.is_active && (
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200/80 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 shadow-2xs whitespace-nowrap">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span>Ativa</span>
          </span>
        )}
      </div>
    </td>
  );
}

interface AcoesProps {
  collection: RagCollection;
  processando: boolean;
  onAtivar: (collection: RagCollection) => void;
  onExcluir: (collection: RagCollection) => void;
}

function AcoesCell({ collection, processando, onAtivar, onExcluir }: AcoesProps) {
  return (
    <td className="py-2.5 px-3 text-center whitespace-nowrap w-20">
      <div className="inline-flex items-center justify-center gap-1.5">
        {!collection.is_active ? (
          <button
            type="button"
            onClick={() => onAtivar(collection)}
            disabled={processando}
            aria-label="Ativar"
            title={`Ativar collection para ${getPurposeLabel(collection.purpose)}`}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-indigo-200/90 bg-indigo-50/70 text-indigo-700 shadow-2xs transition-all hover:bg-indigo-100 hover:text-indigo-900 hover:scale-105 active:scale-95 disabled:opacity-40 cursor-pointer"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2.2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            <span className="sr-only">Ativar</span>
          </button>
        ) : (
          <div className="h-7 w-7" aria-hidden="true" />
        )}
        <button
          type="button"
          onClick={() => onExcluir(collection)}
          disabled={processando || collection.is_active}
          aria-label="Excluir"
          title={
            collection.is_active
              ? `Ative outra collection de ${getPurposeLabel(collection.purpose)} antes de excluir esta.`
              : `Excluir "${collection.name}"`
          }
          className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-red-200/90 bg-red-50/70 text-red-600 shadow-2xs transition-all hover:bg-red-100 hover:text-red-700 hover:scale-105 active:scale-95 disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:scale-100 cursor-pointer"
        >
          <svg
            className="h-4 w-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
            />
          </svg>
          <span className="sr-only">Excluir</span>
        </button>
      </div>
    </td>
  );
}

export function CollectionRow({ collection, processando, onAtivar, onExcluir }: AcoesProps) {
  return (
    <tr className="transition-colors hover:bg-slate-50/60">
      <NomeCell collection={collection} />
      <td className="py-2.5 px-3 whitespace-nowrap">
        <PurposeBadge purpose={collection.purpose} />
      </td>
      <td
        className="py-2.5 px-3 text-slate-700 font-mono text-xs max-w-[140px] truncate"
        title={collection.embedding_model}
      >
        {collection.embedding_model}
      </td>
      <td className="py-2.5 px-3 text-slate-700 text-center">{collection.vector_dimension}</td>
      <td className="py-2.5 px-3 text-slate-700 capitalize whitespace-nowrap">
        {collection.distance_metric}
      </td>
      <td className="py-2.5 px-3 text-slate-600 font-mono text-xs whitespace-nowrap">
        m={collection.hnsw_m} / ef={collection.hnsw_ef_construct}
      </td>
      <td className="py-2.5 px-3 text-slate-700 capitalize whitespace-nowrap">
        {collection.quantization_type}
      </td>
      <td className="py-2.5 px-3 text-slate-700 text-center">{collection.document_count}</td>
      <AcoesCell
        collection={collection}
        processando={processando}
        onAtivar={onAtivar}
        onExcluir={onExcluir}
      />
    </tr>
  );
}
