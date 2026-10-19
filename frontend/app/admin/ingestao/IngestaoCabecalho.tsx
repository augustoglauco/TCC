import { colecoesAtivasPorFinalidade } from "./colecoesAtivas";
import type { RagCollection } from "@/lib/types/rag";

function ChipAtiva({
  collection,
  prefixo,
  title,
  className,
}: {
  collection: RagCollection | undefined;
  prefixo: string;
  title: string;
  className: string;
}) {
  if (!collection) return null;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold border ${className}`}
      title={title}
    >
      ★ {prefixo}: {collection.name}
    </span>
  );
}

/** Cabeçalho visual da página: título, contagem de collections e as ativas por finalidade. */
export function IngestaoCabecalho({ collections }: { collections: RagCollection[] }) {
  const ativas = colecoesAtivasPorFinalidade(collections);
  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs space-y-3">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl sm:text-3xl">📄</span>
            <h1 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
              Ingestão de Documentos &amp; Coleções RAG
            </h1>
          </div>
          <p className="mt-1 text-xs sm:text-sm text-slate-600 max-w-2xl">
            Gestão de documentos indexados, perfis de coleção no Qdrant, varredura web com crawler e
            playground comparativo de busca semântica.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700 border border-blue-100">
            <span>🗂️</span> {collections.length}{" "}
            {collections.length === 1 ? "Collection" : "Collections"}
          </span>
          <ChipAtiva
            collection={ativas.chat}
            prefixo="Chat"
            title="Collection ativa para Chat Público"
            className="bg-emerald-50 text-emerald-700 border-emerald-100"
          />
          <ChipAtiva
            collection={ativas.b2b}
            prefixo="MCP B2B"
            title="Collection ativa para MCP B2B"
            className="bg-purple-50 text-purple-700 border-purple-100"
          />
          <ChipAtiva
            collection={ativas.admin}
            prefixo="Admin"
            title="Collection ativa para Admin"
            className="bg-rose-50 text-rose-700 border-rose-100"
          />
        </div>
      </div>
    </div>
  );
}
