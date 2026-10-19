import { useState } from "react";

import { RagApiError, activateCollection, deleteCollection } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { CollectionPurpose, RagCollection } from "@/lib/types/rag";

export function getPurposeLabel(purpose?: string): string {
  if (purpose === "mcp_b2b") return "MCP B2B";
  if (purpose === "admin") return "Admin";
  return "Chat";
}

interface Params {
  collections: RagCollection[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function useCollectionsTable({ collections, onChanged, onError, onSuccess }: Params) {
  const token = useAuthStore((s) => s.token);
  const [collectionParaExcluir, setCollectionParaExcluir] = useState<RagCollection | null>(null);
  const [processando, setProcessando] = useState(false);
  const [filtroPurpose, setFiltroPurpose] = useState<"todas" | CollectionPurpose>("todas");

  const purposeDe = (c: RagCollection) => c.purpose || "chat";
  const contar = (p: CollectionPurpose) => collections.filter((c) => purposeDe(c) === p).length;

  const collectionsFiltradas =
    filtroPurpose === "todas"
      ? collections
      : collections.filter((c) => purposeDe(c) === filtroPurpose);

  async function executar(acao: () => Promise<void>, mensagemErro: string) {
    setProcessando(true);
    try {
      await acao();
    } catch (err) {
      onError(err instanceof RagApiError ? err.message : mensagemErro);
    } finally {
      setProcessando(false);
    }
  }

  async function handleAtivar(collection: RagCollection) {
    if (!token) return;
    await executar(async () => {
      await activateCollection(token, collection.id);
      onSuccess(
        `"${collection.name}" agora é a collection ativa (${getPurposeLabel(collection.purpose)}).`,
      );
      onChanged();
    }, "Erro inesperado ao ativar a collection.");
  }

  async function confirmarExclusao() {
    if (!collectionParaExcluir || !token) return;
    await executar(async () => {
      await deleteCollection(token, collectionParaExcluir.id);
      onSuccess(`"${collectionParaExcluir.name}" excluída.`);
      setCollectionParaExcluir(null);
      onChanged();
    }, "Erro inesperado ao excluir a collection.");
  }

  return {
    collectionParaExcluir,
    setCollectionParaExcluir,
    processando,
    filtroPurpose,
    setFiltroPurpose,
    chatCount: contar("chat"),
    b2bCount: contar("mcp_b2b"),
    adminCount: contar("admin"),
    collectionsFiltradas,
    handleAtivar,
    confirmarExclusao,
  };
}
