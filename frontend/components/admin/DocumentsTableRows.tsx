"use client";

import { DomainBadge } from "@/components/admin/DomainBadge";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

interface DocumentsTableRowsProps {
  documentos: DocumentRegistryEntry[];
  onVisualizar: (documento: DocumentRegistryEntry) => void;
  onReingerir: (documento: DocumentRegistryEntry) => void;
  onExcluir: (documento: DocumentRegistryEntry) => void;
}

export function DocumentsEmpty({ onLimpar }: { onLimpar: () => void }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center space-y-2">
      <p className="text-sm font-medium text-slate-700">
        Nenhum documento encontrado com os filtros selecionados.
      </p>
      <button
        type="button"
        onClick={onLimpar}
        className="text-xs font-semibold text-blue-600 hover:underline"
      >
        Limpar filtros
      </button>
    </div>
  );
}

function DocumentoRow({
  documento,
  onVisualizar,
  onReingerir,
  onExcluir,
}: Omit<DocumentsTableRowsProps, "documentos"> & { documento: DocumentRegistryEntry }) {
  return (
    <tr className="transition-colors hover:bg-slate-50/60">
      <td className="py-3.5 px-4 font-semibold text-slate-900">
        <button
          type="button"
          onClick={() => onVisualizar(documento)}
          className="group inline-flex items-center gap-1.5 text-left text-slate-900 hover:text-blue-600 transition-colors focus:outline-none"
        >
          <span className="underline decoration-slate-300 group-hover:decoration-blue-500 underline-offset-2">
            {documento.filename}
          </span>
          <span className="opacity-0 group-hover:opacity-100 text-xs text-blue-500 transition-opacity">
            ↗
          </span>
        </button>
      </td>
      <td className="py-3.5 px-4">
        <DomainBadge domain={documento.domain} />
      </td>
      <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">{documento.chunk_count}</td>
      <td className="py-3.5 px-4 text-slate-700">{documento.collection_name || "-"}</td>
      <td className="py-3.5 px-4 text-slate-500 text-xs whitespace-nowrap">
        {new Date(documento.created_at).toLocaleDateString("pt-BR")}
      </td>
      <td className="py-3.5 px-4 text-right whitespace-nowrap">
        <button
          type="button"
          onClick={() => onReingerir(documento)}
          className="mr-2 inline-flex items-center gap-1 rounded-lg border border-indigo-200/80 bg-indigo-50/50 px-2.5 py-1 text-xs font-semibold text-indigo-700 shadow-2xs transition-colors hover:bg-indigo-100/80 hover:text-indigo-800"
        >
          Reingerir
        </button>
        <button
          type="button"
          onClick={() => onExcluir(documento)}
          className="inline-flex items-center gap-1 rounded-lg border border-red-200/80 bg-red-50/50 px-2.5 py-1 text-xs font-semibold text-red-600 shadow-2xs transition-colors hover:bg-red-100/80 hover:text-red-700"
        >
          Excluir
        </button>
      </td>
    </tr>
  );
}

export function DocumentsTableRows({ documentos, ...acoes }: DocumentsTableRowsProps) {
  return (
    <div className="overflow-x-auto max-h-[50vh] sm:max-h-[60vh] overflow-y-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
      <table className="w-full min-w-[700px] text-left text-sm">
        <thead className="sticky top-0 z-10 bg-slate-50 border-b border-slate-200/80 shadow-2xs">
          <tr className="text-[11px] uppercase tracking-wider font-semibold text-slate-500">
            <th className="py-3 px-4">Arquivo</th>
            <th className="py-3 px-4">Domínio</th>
            <th className="py-3 px-4">Chunks</th>
            <th className="py-3 px-4">Collection</th>
            <th className="py-3 px-4">Data</th>
            <th className="py-3 px-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {documentos.map((documento) => (
            <DocumentoRow key={documento.id} documento={documento} {...acoes} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
