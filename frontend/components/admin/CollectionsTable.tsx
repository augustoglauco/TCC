"use client";

import { useState } from "react";

import { Modal } from "@/components/ui/Modal";
import { RagApiError, activateCollection, deleteCollection } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { CollectionPurpose, RagCollection } from "@/lib/types/rag";

export interface CollectionsTableProps {
  collections: RagCollection[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

function getPurposeLabel(purpose?: string): string {
  if (purpose === "mcp_b2b") return "MCP B2B";
  if (purpose === "admin") return "Admin";
  return "Chat";
}

export function CollectionsTable({
  collections,
  onChanged,
  onError,
  onSuccess,
}: CollectionsTableProps) {
  const token = useAuthStore((s) => s.token);
  const [collectionParaExcluir, setCollectionParaExcluir] = useState<RagCollection | null>(null);
  const [processando, setProcessando] = useState(false);
  const [filtroPurpose, setFiltroPurpose] = useState<"todas" | CollectionPurpose>("todas");

  const chatCount = collections.filter((c) => (c.purpose || "chat") === "chat").length;
  const b2bCount = collections.filter((c) => c.purpose === "mcp_b2b").length;
  const adminCount = collections.filter((c) => c.purpose === "admin").length;

  const collectionsFiltradas =
    filtroPurpose === "todas"
      ? collections
      : collections.filter((c) => (c.purpose || "chat") === filtroPurpose);

  async function handleAtivar(collection: RagCollection) {
    if (!token) return;
    setProcessando(true);
    try {
      await activateCollection(token, collection.id);
      onSuccess(`"${collection.name}" agora é a collection ativa (${getPurposeLabel(collection.purpose)}).`);
      onChanged();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : "Erro inesperado ao ativar a collection.");
    } finally {
      setProcessando(false);
    }
  }

  async function confirmarExclusao() {
    if (!collectionParaExcluir || !token) return;
    setProcessando(true);
    try {
      await deleteCollection(token, collectionParaExcluir.id);
      onSuccess(`"${collectionParaExcluir.name}" excluída.`);
      setCollectionParaExcluir(null);
      onChanged();
    } catch (err) {
      onError(
        err instanceof RagApiError ? err.message : "Erro inesperado ao excluir a collection.",
      );
    } finally {
      setProcessando(false);
    }
  }

  if (collections.length === 0) {
    return <p className="text-sm text-gray-600">Nenhuma collection criada ainda.</p>;
  }

  return (
    <>
      {/* Filtro por Finalidade */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">
          Finalidade:
        </span>
        <button
          type="button"
          onClick={() => setFiltroPurpose("todas")}
          className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
            filtroPurpose === "todas"
              ? "bg-slate-900 text-white shadow-2xs"
              : "bg-slate-100 text-slate-600 hover:bg-slate-200/80"
          }`}
        >
          Todas ({collections.length})
        </button>
        <button
          type="button"
          onClick={() => setFiltroPurpose("chat")}
          className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
            filtroPurpose === "chat"
              ? "bg-blue-600 text-white shadow-2xs"
              : "bg-blue-50 text-blue-700 hover:bg-blue-100/80"
          }`}
        >
          💬 Chat ({chatCount})
        </button>
        <button
          type="button"
          onClick={() => setFiltroPurpose("mcp_b2b")}
          className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
            filtroPurpose === "mcp_b2b"
              ? "bg-purple-600 text-white shadow-2xs"
              : "bg-purple-50 text-purple-700 hover:bg-purple-100/80"
          }`}
        >
          🏢 MCP B2B ({b2bCount})
        </button>
        <button
          type="button"
          onClick={() => setFiltroPurpose("admin")}
          className={`rounded-lg px-2.5 py-1 text-xs font-semibold transition-all ${
            filtroPurpose === "admin"
              ? "bg-rose-600 text-white shadow-2xs"
              : "bg-rose-50 text-rose-700 hover:bg-rose-100/80"
          }`}
        >
          🛡️ Admin ({adminCount})
        </button>
      </div>

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
            {collectionsFiltradas.map((collection) => (
              <tr key={collection.id} className="transition-colors hover:bg-slate-50/60">
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
                <td className="py-2.5 px-3 whitespace-nowrap">
                  {collection.purpose === "mcp_b2b" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-purple-200/80 bg-purple-50 px-2.5 py-0.5 text-xs font-semibold text-purple-700 shadow-2xs">
                      MCP B2B
                    </span>
                  ) : collection.purpose === "admin" ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-rose-200/80 bg-rose-50 px-2.5 py-0.5 text-xs font-semibold text-rose-700 shadow-2xs">
                      Admin
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200/80 bg-slate-50 px-2.5 py-0.5 text-xs font-semibold text-slate-600 shadow-2xs">
                      Chat
                    </span>
                  )}
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
                <td className="py-2.5 px-3 text-center whitespace-nowrap w-20">
                  <div className="inline-flex items-center justify-center gap-1.5">
                    {!collection.is_active ? (
                      <button
                        type="button"
                        onClick={() => handleAtivar(collection)}
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
                      onClick={() => setCollectionParaExcluir(collection)}
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
        Tem certeza que deseja excluir &ldquo;{collectionParaExcluir?.name}&rdquo;? Isso vai apagar
        em cascata os {collectionParaExcluir?.document_count} documento(s) ingerido(s) nela e não
        pode ser desfeito.
      </Modal>
    </>
  );
}
