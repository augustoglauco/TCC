"use client";

import { useState } from "react";

import { DocumentViewModal } from "@/components/admin/DocumentViewModal";
import { DomainBadge } from "@/components/admin/DomainBadge";
import { ReingestModal } from "@/components/admin/ReingestModal";
import { Modal } from "@/components/ui/Modal";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  collections: RagCollection[];
  onDeleted: (id: string) => void;
  onReingested: () => void;
}

export function DocumentsTable({ documents, collections, onDeleted, onReingested }: DocumentsTableProps) {
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(null);
  const [documentoParaReingerir, setDocumentoParaReingerir] = useState<DocumentRegistryEntry | null>(null);
  const [documentoParaVisualizar, setDocumentoParaVisualizar] = useState<DocumentRegistryEntry | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  async function confirmarExclusao() {
    if (!documentoParaExcluir) return;
    setExcluindo(true);
    try {
      await deleteDocument(documentoParaExcluir.id);
      showToast(`"${documentoParaExcluir.filename}" excluído.`, "success");
      onDeleted(documentoParaExcluir.id);
      setDocumentoParaExcluir(null);
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao excluir o documento.",
        "error",
      );
    } finally {
      setExcluindo(false);
    }
  }

  if (documents.length === 0) {
    return <p className="text-sm text-gray-600">Nenhum documento ingerido ainda.</p>;
  }

  return (
    <>
      <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
              <th className="py-3 px-4">Arquivo</th>
              <th className="py-3 px-4">Domínio</th>
              <th className="py-3 px-4">Chunks</th>
              <th className="py-3 px-4">Collection</th>
              <th className="py-3 px-4">Data</th>
              <th className="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {documents.map((documento) => (
              <tr key={documento.id} className="transition-colors hover:bg-slate-50/60">
                <td className="py-3.5 px-4 font-semibold text-slate-900">
                  <button
                    type="button"
                    onClick={() => setDocumentoParaVisualizar(documento)}
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
                    onClick={() => setDocumentoParaReingerir(documento)}
                    className="mr-2 inline-flex items-center gap-1 rounded-lg border border-indigo-200/80 bg-indigo-50/50 px-2.5 py-1 text-xs font-semibold text-indigo-700 shadow-2xs transition-colors hover:bg-indigo-100/80 hover:text-indigo-800"
                  >
                    Reingerir
                  </button>
                  <button
                    type="button"
                    onClick={() => setDocumentoParaExcluir(documento)}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-200/80 bg-red-50/50 px-2.5 py-1 text-xs font-semibold text-red-600 shadow-2xs transition-colors hover:bg-red-100/80 hover:text-red-700"
                  >
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <DocumentViewModal
        documento={documentoParaVisualizar}
        onOpenChange={(open) => !open && setDocumentoParaVisualizar(null)}
      />

      <Modal
        open={documentoParaExcluir !== null}
        onOpenChange={(open) => !open && setDocumentoParaExcluir(null)}
        title="Excluir documento"
        footer={
          <>
            <button
              type="button"
              onClick={() => setDocumentoParaExcluir(null)}
              className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={confirmarExclusao}
              disabled={excluindo}
              className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Confirmar exclusão
            </button>
          </>
        }
      >
        Tem certeza que deseja excluir &ldquo;{documentoParaExcluir?.filename}&rdquo;? Os chunks
        já indexados serão removidos do RAG e essa ação não pode ser desfeita.
      </Modal>

      <ReingestModal
        documento={documentoParaReingerir}
        collections={collections}
        onOpenChange={(open) => !open && setDocumentoParaReingerir(null)}
        onReingested={() => {
          setDocumentoParaReingerir(null);
          showToast("Documento reingerido.", "success");
          onReingested();
        }}
        onError={(message) => showToast(message, "error")}
      />

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </>
  );
}

