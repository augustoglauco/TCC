"use client";

import { useMemo, useState } from "react";

import { DocumentViewModal } from "@/components/admin/DocumentViewModal";
import { DomainBadge } from "@/components/admin/DomainBadge";
import { ReingestModal } from "@/components/admin/ReingestModal";
import { Modal } from "@/components/ui/Modal";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

export interface DocumentsTableProps {
  documents: DocumentRegistryEntry[];
  collections: RagCollection[];
  onDeleted: (id: string) => void;
  onReingested: () => void;
}

export function DocumentsTable({
  documents,
  collections,
  onDeleted,
  onReingested,
}: DocumentsTableProps) {
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(
    null,
  );
  const [documentoParaReingerir, setDocumentoParaReingerir] =
    useState<DocumentRegistryEntry | null>(null);
  const [documentoParaVisualizar, setDocumentoParaVisualizar] =
    useState<DocumentRegistryEntry | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

  // Estados dos filtros
  const [filtroNome, setFiltroNome] = useState("");
  const [dominiosSelecionados, setDominiosSelecionados] = useState<RagDomain[]>([]);
  const [collectionIdSelecionada, setCollectionIdSelecionada] = useState("");
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");

  const handleToggleDomain = (domain: RagDomain) => {
    setDominiosSelecionados((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain],
    );
  };

  const temFiltroAtivo = Boolean(
    filtroNome.trim() ||
      dominiosSelecionados.length > 0 ||
      collectionIdSelecionada ||
      dataInicio ||
      dataFim,
  );

  const limparFiltros = () => {
    setFiltroNome("");
    setDominiosSelecionados([]);
    setCollectionIdSelecionada("");
    setDataInicio("");
    setDataFim("");
  };

  const documentosFiltrados = useMemo(() => {
    return documents.filter((doc) => {
      // 1. Nome do arquivo
      if (filtroNome.trim()) {
        if (!doc.filename.toLowerCase().includes(filtroNome.trim().toLowerCase())) {
          return false;
        }
      }

      // 2. Domínio(s)
      if (dominiosSelecionados.length > 0) {
        if (!dominiosSelecionados.includes(doc.domain)) {
          return false;
        }
      }

      // 3. Collection
      if (collectionIdSelecionada) {
        if (doc.collection_id !== collectionIdSelecionada) {
          return false;
        }
      }

      // 4. Range de data
      if (dataInicio || dataFim) {
        const docDateStr = doc.created_at.slice(0, 10);
        if (dataInicio && docDateStr < dataInicio) {
          return false;
        }
        if (dataFim && docDateStr > dataFim) {
          return false;
        }
      }

      return true;
    });
  }, [documents, filtroNome, dominiosSelecionados, collectionIdSelecionada, dataInicio, dataFim]);

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
      {/* Área de Filtros */}
      <div className="mb-5 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
          {/* 1. Nome do arquivo */}
          <div className="md:col-span-4 space-y-1">
            <label
              htmlFor="filtro-nome"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
            >
              Nome do arquivo
            </label>
            <div className="relative">
              <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 text-xs">
                🔍
              </span>
              <input
                id="filtro-nome"
                type="text"
                value={filtroNome}
                onChange={(e) => setFiltroNome(e.target.value)}
                placeholder="Buscar por nome do arquivo..."
                className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* 2. Collection */}
          <div className="md:col-span-3 space-y-1">
            <label
              htmlFor="filtro-collection"
              className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
            >
              Collection
            </label>
            <select
              id="filtro-collection"
              aria-label="Collection"
              value={collectionIdSelecionada}
              onChange={(e) => setCollectionIdSelecionada(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Todas as collections</option>
              {collections.map((col) => (
                <option key={col.id} value={col.id}>
                  {col.name} {col.is_active ? "(Ativa)" : ""}
                </option>
              ))}
            </select>
          </div>

          {/* 3. Range de data */}
          <div className="md:col-span-5 space-y-1">
            <span className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
              Range de data
            </span>
            <div className="flex items-center gap-2">
              <div className="flex-1 flex items-center gap-1.5">
                <label
                  htmlFor="filtro-data-inicio"
                  className="text-xs text-slate-500 font-medium shrink-0"
                >
                  De:
                </label>
                <input
                  id="filtro-data-inicio"
                  aria-label="De:"
                  type="date"
                  value={dataInicio}
                  onChange={(e) => setDataInicio(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-1.5 px-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="flex-1 flex items-center gap-1.5">
                <label
                  htmlFor="filtro-data-fim"
                  className="text-xs text-slate-500 font-medium shrink-0"
                >
                  Até:
                </label>
                <input
                  id="filtro-data-fim"
                  aria-label="Até:"
                  type="date"
                  value={dataFim}
                  onChange={(e) => setDataFim(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-1.5 px-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Linha inferior: Domínios (pills múltiplos) e Contagem / Limpar */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-200/60">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-slate-600 mr-1">Domínios:</span>
            {DOMAIN_OPTIONS.map((opt) => {
              const isSelected = dominiosSelecionados.includes(opt.value);
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => handleToggleDomain(opt.value)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                    isSelected
                      ? "bg-blue-600 text-white shadow-xs ring-2 ring-blue-600/30"
                      : "bg-white text-slate-700 border border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>

          <div className="flex items-center gap-3 ml-auto">
            <span className="text-xs text-slate-500">
              Exibindo{" "}
              <span className="font-semibold text-slate-800">{documentosFiltrados.length}</span> de{" "}
              <span className="font-semibold text-slate-800">{documents.length}</span> documentos
            </span>
            {temFiltroAtivo && (
              <button
                type="button"
                onClick={limparFiltros}
                className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline transition-colors"
              >
                Limpar filtros
              </button>
            )}
          </div>
        </div>
      </div>

      {documentosFiltrados.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center space-y-2">
          <p className="text-sm font-medium text-slate-700">
            Nenhum documento encontrado com os filtros selecionados.
          </p>
          <button
            type="button"
            onClick={limparFiltros}
            className="text-xs font-semibold text-blue-600 hover:underline"
          >
            Limpar filtros
          </button>
        </div>
      ) : (
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
              {documentosFiltrados.map((documento) => (
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
                <td className="py-3.5 px-4 text-slate-700 font-mono text-xs">
                  {documento.chunk_count}
                </td>
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
      )}

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
        Tem certeza que deseja excluir &ldquo;{documentoParaExcluir?.filename}&rdquo;? Os chunks já
        indexados serão removidos do RAG e essa ação não pode ser desfeita.
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
