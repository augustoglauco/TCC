"use client";

import { useMemo, useState } from "react";

import { useToast } from "@/components/ui/Toast";
import { RagApiError, deleteDocument } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { DocumentRegistryEntry, RagDomain } from "@/lib/types/rag";

interface FiltrosDocumentos {
  nome: string;
  dominios: RagDomain[];
  collectionId: string;
  dataInicio: string;
  dataFim: string;
}

function passaNoFiltro(doc: DocumentRegistryEntry, f: FiltrosDocumentos): boolean {
  const nome = f.nome.trim().toLowerCase();
  if (nome && !doc.filename.toLowerCase().includes(nome)) return false;
  if (f.dominios.length > 0 && !f.dominios.includes(doc.domain)) return false;
  if (f.collectionId && doc.collection_id !== f.collectionId) return false;
  const dia = doc.created_at.slice(0, 10);
  if (f.dataInicio && dia < f.dataInicio) return false;
  if (f.dataFim && dia > f.dataFim) return false;
  return true;
}

export function useDocumentsTable(
  documents: DocumentRegistryEntry[],
  onDeleted: (id: string) => void,
) {
  const token = useAuthStore((s) => s.token);
  const [documentoParaExcluir, setDocumentoParaExcluir] = useState<DocumentRegistryEntry | null>(
    null,
  );
  const [documentoParaReingerir, setDocumentoParaReingerir] =
    useState<DocumentRegistryEntry | null>(null);
  const [documentoParaVisualizar, setDocumentoParaVisualizar] =
    useState<DocumentRegistryEntry | null>(null);
  const [excluindo, setExcluindo] = useState(false);
  const { toasts, showToast, dismissToast } = useToast();

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
    const filtros = {
      nome: filtroNome,
      dominios: dominiosSelecionados,
      collectionId: collectionIdSelecionada,
      dataInicio,
      dataFim,
    };
    return documents.filter((doc) => passaNoFiltro(doc, filtros));
  }, [documents, filtroNome, dominiosSelecionados, collectionIdSelecionada, dataInicio, dataFim]);

  async function confirmarExclusao() {
    if (!documentoParaExcluir || !token) return;
    setExcluindo(true);
    try {
      await deleteDocument(token, documentoParaExcluir.id);
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

  return {
    toasts,
    showToast,
    dismissToast,
    documentoParaExcluir,
    setDocumentoParaExcluir,
    documentoParaReingerir,
    setDocumentoParaReingerir,
    documentoParaVisualizar,
    setDocumentoParaVisualizar,
    excluindo,
    confirmarExclusao,
    filtroNome,
    setFiltroNome,
    dominiosSelecionados,
    handleToggleDomain,
    collectionIdSelecionada,
    setCollectionIdSelecionada,
    dataInicio,
    setDataInicio,
    dataFim,
    setDataFim,
    temFiltroAtivo,
    limparFiltros,
    documentosFiltrados,
  };
}
