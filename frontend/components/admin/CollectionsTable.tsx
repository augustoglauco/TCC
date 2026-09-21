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
      <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-xs">
        <table className="w-full min-w-[700px] text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200/80 bg-slate-50/80 text-[11px] uppercase tracking-wider font-semibold text-slate-500">
              <th className="py-3 px-4">Nome</th>
              <th className="py-3 px-4">Finalidade</th>
              <th className="py-3 px-4">Modelo</th>
              <th className="py-3 px-4">Dimensão</th>
              <th className="py-3 px-4">Métrica</th>
              <th className="py-3 px-4">HNSW</th>
              <th className="py-3 px-4">Quantização</th>
              <th className="py-3 px-4">Documentos</th>
              <th className="py-3 px-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {collections.map((collection) => (
              <tr key={collection.id} className="transition-colors hover:bg-slate-50/60">
                <td className="py-3.5 px-4 font-semibold text-slate-900">
                  <div className="inline-flex items-center gap-2">
                    <span>{collection.name}</span>
                    {collection.is_active && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200/80 bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 shadow-2xs">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                        Ativa
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-3.5 px-4">
                  {collection.purpose === "mcp_b2b" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-purple-200/80 bg-purple-50 px-2.5 py-0.5 text-xs font-semibold text-purple-700 shadow-2xs">
                      MCP B2B
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200/80 bg-slate-50 px-2.5 py-0.5 text-xs font-semibold text-slate-600 shadow-2xs">
                      Chat
                    </span>
                  )}
                </td>
                <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">{collection.embedding_model}</td>
                <td className="py-3.5 px-4 text-slate-700">{collection.vector_dimension}</td>
                <td className="py-3.5 px-4 text-slate-700 capitalize">{collection.distance_metric}</td>
                <td className="py-3.5 px-4 text-slate-600 font-mono text-xs">
                  m={collection.hnsw_m} / ef={collection.hnsw_ef_construct}
                </td>
                <td className="py-3.5 px-4 text-slate-700 capitalize">{collection.quantization_type}</td>
                <td className="py-3.5 px-4 text-slate-700">{collection.document_count}</td>
                <td className="py-3.5 px-4 text-right whitespace-nowrap">
                  {!collection.is_active &&
                    (collection.purpose === "mcp_b2b" ? (
                      <button
                        type="button"
                        disabled
                        title="Collections do MCP B2B não podem ser ativadas para o chat."
                        className="mr-2 inline-flex cursor-not-allowed items-center gap-1 rounded-lg border border-slate-200/80 bg-slate-50/50 px-2.5 py-1 text-xs font-semibold text-slate-400 shadow-2xs"
                      >
                        Ativar
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleAtivar(collection)}
                        disabled={processando}
                        className="mr-2 inline-flex items-center gap-1 rounded-lg border border-indigo-200/80 bg-indigo-50/50 px-2.5 py-1 text-xs font-semibold text-indigo-700 shadow-2xs transition-colors hover:bg-indigo-100/80 hover:text-indigo-800 disabled:opacity-50"
                      >
                        Ativar
                      </button>
                    ))}
                  <button
                    type="button"
                    onClick={() => setCollectionParaExcluir(collection)}
                    disabled={processando || collection.is_active}
                    title={collection.is_active ? "Ative outra collection antes de excluir esta." : undefined}
                    className="inline-flex items-center gap-1 rounded-lg border border-red-200/80 bg-red-50/50 px-2.5 py-1 text-xs font-semibold text-red-600 shadow-2xs transition-colors hover:bg-red-100/80 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Excluir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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
