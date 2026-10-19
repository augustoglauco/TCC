"use client";

import { DocumentViewModal } from "@/components/admin/DocumentViewModal";
import { DocumentsEmpty, DocumentsTableRows } from "@/components/admin/DocumentsTableRows";
import { DocumentsFilterBar } from "@/components/admin/DocumentsFilterBar";
import { ReingestModal } from "@/components/admin/ReingestModal";
import { Modal } from "@/components/ui/Modal";
import { ToastStack } from "@/components/ui/Toast";
import { useDocumentsTable } from "@/lib/hooks/useDocumentsTable";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  collections: RagCollection[];
  onDeleted: (id: string) => void;
  onReingested: () => void;
}

interface ExcluirDocumentoModalProps {
  documento: DocumentRegistryEntry | null;
  excluindo: boolean;
  onCancelar: () => void;
  onConfirmar: () => void;
}

function ExcluirDocumentoModal({
  documento,
  excluindo,
  onCancelar,
  onConfirmar,
}: ExcluirDocumentoModalProps) {
  return (
    <Modal
      open={documento !== null}
      onOpenChange={(open) => !open && onCancelar()}
      title="Excluir documento"
      footer={
        <>
          <button
            type="button"
            onClick={onCancelar}
            className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirmar}
            disabled={excluindo}
            className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Confirmar exclusão
          </button>
        </>
      }
    >
      Tem certeza que deseja excluir &ldquo;{documento?.filename}&rdquo;? Os chunks já indexados
      serão removidos do RAG e essa ação não pode ser desfeita.
    </Modal>
  );
}

export function DocumentsTable({
  documents,
  collections,
  onDeleted,
  onReingested,
}: DocumentsTableProps) {
  const t = useDocumentsTable(documents, onDeleted);

  if (documents.length === 0) {
    return <p className="text-sm text-gray-600">Nenhum documento ingerido ainda.</p>;
  }

  return (
    <>
      <DocumentsFilterBar
        filtroNome={t.filtroNome}
        dominiosSelecionados={t.dominiosSelecionados}
        collectionIdSelecionada={t.collectionIdSelecionada}
        dataInicio={t.dataInicio}
        dataFim={t.dataFim}
        collections={collections}
        totalDocumentos={documents.length}
        totalFiltrados={t.documentosFiltrados.length}
        temFiltroAtivo={t.temFiltroAtivo}
        onFiltroNome={t.setFiltroNome}
        onToggleDomain={t.handleToggleDomain}
        onCollectionChange={t.setCollectionIdSelecionada}
        onDataInicio={t.setDataInicio}
        onDataFim={t.setDataFim}
        onLimpar={t.limparFiltros}
      />

      {t.documentosFiltrados.length === 0 ? (
        <DocumentsEmpty onLimpar={t.limparFiltros} />
      ) : (
        <DocumentsTableRows
          documentos={t.documentosFiltrados}
          onVisualizar={t.setDocumentoParaVisualizar}
          onReingerir={t.setDocumentoParaReingerir}
          onExcluir={t.setDocumentoParaExcluir}
        />
      )}

      <DocumentViewModal
        documento={t.documentoParaVisualizar}
        onOpenChange={(open) => !open && t.setDocumentoParaVisualizar(null)}
      />

      <ExcluirDocumentoModal
        documento={t.documentoParaExcluir}
        excluindo={t.excluindo}
        onCancelar={() => t.setDocumentoParaExcluir(null)}
        onConfirmar={t.confirmarExclusao}
      />

      <ReingestModal
        documento={t.documentoParaReingerir}
        collections={collections}
        onOpenChange={(open) => !open && t.setDocumentoParaReingerir(null)}
        onReingested={() => {
          t.setDocumentoParaReingerir(null);
          t.showToast("Documento reingerido.", "success");
          onReingested();
        }}
        onError={(message) => t.showToast(message, "error")}
      />

      <ToastStack toasts={t.toasts} onDismiss={t.dismissToast} />
    </>
  );
}
