"use client";

import { Modal } from "@/components/ui/Modal";
import { useCollectionsTable } from "@/lib/hooks/useCollectionsTable";
import type { RagCollection } from "@/lib/types/rag";
import { CollectionRow } from "./CollectionRow";
import { CollectionsPurposeFilter } from "./CollectionsPurposeFilter";

export interface CollectionsTableProps {
  collections: RagCollection[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

interface ModalExclusaoProps {
  collection: RagCollection | null;
  processando: boolean;
  onCancelar: () => void;
  onConfirmar: () => void;
}

function ModalExclusao({ collection, processando, onCancelar, onConfirmar }: ModalExclusaoProps) {
  return (
    <Modal
      open={collection !== null}
      onOpenChange={(open) => !open && onCancelar()}
      title="Excluir collection"
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
            disabled={processando}
            className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            Confirmar exclusão
          </button>
        </>
      }
    >
      Tem certeza que deseja excluir &ldquo;{collection?.name}&rdquo;? Isso vai apagar em cascata os{" "}
      {collection?.document_count} documento(s) ingerido(s) nela e não pode ser desfeito.
    </Modal>
  );
}

export function CollectionsTable({
  collections,
  onChanged,
  onError,
  onSuccess,
}: CollectionsTableProps) {
  const t = useCollectionsTable({ collections, onChanged, onError, onSuccess });

  if (collections.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma collection criada ainda.</p>;
  }

  return (
    <>
      <CollectionsPurposeFilter
        filtroPurpose={t.filtroPurpose}
        totalCount={collections.length}
        chatCount={t.chatCount}
        b2bCount={t.b2bCount}
        adminCount={t.adminCount}
        onChange={t.setFiltroPurpose}
      />

      <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
              <th className="py-2.5 px-3">Nome</th>
              <th className="py-2.5 px-3">Finalidade</th>
              <th className="py-2.5 px-3">Modelo</th>
              <th className="py-2.5 px-3 text-center">Dimensão</th>
              <th className="py-2.5 px-3">Métrica</th>
              <th className="py-2.5 px-3">HNSW</th>
              <th className="py-2.5 px-3">Quantização</th>
              <th className="py-2.5 px-3 text-center">Documentos</th>
              <th className="py-2.5 px-3 text-center w-20">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {t.collectionsFiltradas.map((collection) => (
              <CollectionRow
                key={collection.id}
                collection={collection}
                processando={t.processando}
                onAtivar={t.handleAtivar}
                onExcluir={t.setCollectionParaExcluir}
              />
            ))}
          </tbody>
        </table>
      </div>

      <ModalExclusao
        collection={t.collectionParaExcluir}
        processando={t.processando}
        onCancelar={() => t.setCollectionParaExcluir(null)}
        onConfirmar={t.confirmarExclusao}
      />
    </>
  );
}
