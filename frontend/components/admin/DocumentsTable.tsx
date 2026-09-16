"use client";

import { useState } from "react";

import { DomainBadge } from "@/components/admin/DomainBadge";
import { ReingestModal } from "@/components/admin/ReingestModal";
import { Modal } from "@/components/ui/Modal";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDias <= 0) return "hoje";
  if (diffDias === 1) return "há 1 dia";
  return `há ${diffDias} dias`;
}

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  collections: RagCollection[];
  onDeleted: (id: string) => void;
  onReingested: () => void;
}

export function DocumentsTable({ documents, collections, onDeleted, onReingested }: DocumentsTableProps) {
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(null);
  const [documentoParaReingerir, setDocumentoParaReingerir] = useState<DocumentRegistryEntry | null>(null);
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
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2 pr-4">Arquivo</th>
            <th className="py-2 pr-4">Domínio</th>
            <th className="py-2 pr-4">Chunks</th>
            <th className="py-2 pr-4">Collection</th>
            <th className="py-2 pr-4">Data</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {documents.map((documento) => (
            <tr key={documento.id} className="border-b border-gray-100">
              <td className="py-2 pr-4 text-gray-900">{documento.filename}</td>
              <td className="py-2 pr-4">
                <DomainBadge domain={documento.domain} />
              </td>
              <td className="py-2 pr-4 text-gray-700">{documento.chunk_count}</td>
              <td className="py-2 pr-4 text-gray-700">{documento.collection_name}</td>
              <td className="py-2 pr-4 text-gray-500" title={documento.created_at}>
                {formatarDataRelativa(documento.created_at)}
              </td>
              <td className="py-2 pr-4 text-right">
                <button
                  type="button"
                  onClick={() => setDocumentoParaReingerir(documento)}
                  className="mr-3 text-gray-700 hover:text-gray-900"
                >
                  Reingerir
                </button>
                <button
                  type="button"
                  onClick={() => setDocumentoParaExcluir(documento)}
                  className="text-red-600 hover:text-red-800"
                >
                  Excluir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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
