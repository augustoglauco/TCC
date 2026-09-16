"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, activateCollection, deleteCollection } from "@/lib/api/rag";
import type { RagCollection } from "@/lib/types/rag";

export interface CollectionsTableProps {
  collections: RagCollection[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function CollectionsTable({ collections, onChanged, onError, onSuccess }: CollectionsTableProps) {
  const [collectionParaExcluir, setCollectionParaExcluir] = useState<RagCollection | null>(null);
  const [processando, setProcessando] = useState(false);

  async function handleAtivar(collection: RagCollection) {
    setProcessando(true);
    try {
      await activateCollection(collection.id);
      onSuccess(`"${collection.name}" agora é a collection ativa.`);
      onChanged();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao ativar a collection.");
    } finally {
      setProcessando(false);
    }
  }

  async function confirmarExclusao() {
    if (!collectionParaExcluir) return;
    setProcessando(true);
    try {
      await deleteCollection(collectionParaExcluir.id);
      onSuccess(`"${collectionParaExcluir.name}" excluída.`);
      setCollectionParaExcluir(null);
      onChanged();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao excluir a collection.");
    } finally {
      setProcessando(false);
    }
  }

  if (collections.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma collection criada ainda.</p>;
  }

  return (
    <>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-gray-200 text-gray-500">
            <th className="py-2 pr-4">Nome</th>
            <th className="py-2 pr-4">Modelo</th>
            <th className="py-2 pr-4">Dimensão</th>
            <th className="py-2 pr-4">Métrica</th>
            <th className="py-2 pr-4">HNSW</th>
            <th className="py-2 pr-4">Quantização</th>
            <th className="py-2 pr-4">Documentos</th>
            <th className="py-2 pr-4" />
          </tr>
        </thead>
        <tbody>
          {collections.map((collection) => (
            <tr key={collection.id} className="border-b border-gray-100">
              <td className="py-2 pr-4 text-gray-900">
                {collection.name}
                {collection.is_active && (
                  <span className="ml-2 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800">
                    Ativa
                  </span>
                )}
              </td>
              <td className="py-2 pr-4 text-gray-700">{collection.embedding_model}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.vector_dimension}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.distance_metric}</td>
              <td className="py-2 pr-4 text-gray-700">
                m={collection.hnsw_m} / ef={collection.hnsw_ef_construct}
              </td>
              <td className="py-2 pr-4 text-gray-700">{collection.quantization_type}</td>
              <td className="py-2 pr-4 text-gray-700">{collection.document_count}</td>
              <td className="py-2 pr-4 text-right">
                {!collection.is_active && (
                  <button
                    type="button"
                    onClick={() => handleAtivar(collection)}
                    disabled={processando}
                    className="mr-3 text-gray-700 hover:text-gray-900"
                  >
                    Ativar
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setCollectionParaExcluir(collection)}
                  disabled={processando || collection.is_active}
                  title={collection.is_active ? "Ative outra collection antes de excluir esta." : undefined}
                  className="text-red-600 hover:text-red-800 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Excluir
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Modal
        open={collectionParaExcluir !== null}
        onOpenChange={(open) => !open && setCollectionParaExcluir(null)}
        title="Excluir collection"
        footer={
          <>
            <button
              type="button"
              onClick={() => setCollectionParaExcluir(null)}
              className="rounded-md px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={confirmarExclusao}
              disabled={processando}
              className="rounded-md bg-red-600 px-4 py-2 text-sm text-white disabled:opacity-50"
            >
              Confirmar exclusão
            </button>
          </>
        }
      >
        Tem certeza que deseja excluir &ldquo;{collectionParaExcluir?.name}&rdquo;? Isso vai apagar em
        cascata os {collectionParaExcluir?.document_count} documento(s) ingerido(s) nela e não pode ser
        desfeito.
      </Modal>
    </>
  );
}
