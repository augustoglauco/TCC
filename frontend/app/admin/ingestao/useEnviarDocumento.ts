import { useState } from "react";

import { useCollectionActions } from "./useCollectionActions";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { RagApiError, uploadDocument } from "@/lib/api/rag";
import type { DocumentIngestResponse, RagCollection, RagDomain } from "@/lib/types/rag";

interface Params {
  collections: RagCollection[];
  onColecoesMudaram: () => Promise<RagCollection[]>;
  onIngerido: () => void;
}

/** Estado e ações da aba "Enviar documento" (arquivo, domínio, collection e envio). */
export function useEnviarDocumento({ collections, onColecoesMudaram, onIngerido }: Params) {
  const token = useAuthStore((s) => s.token);
  const [file, setFile] = useState<File | null>(null);
  const [domain, setDomain] = useState<RagDomain>("vendas");
  const [collectionId, setCollectionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<DocumentIngestResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const collectionAtiva = collections.find((collection) => collection.is_active);
  const collectionSelecionadaObj =
    collections.find((c) => c.id === collectionId) || collectionAtiva || collections[0];
  const collectionSelecionada = collections.some((collection) => collection.id === collectionId)
    ? collectionId
    : collectionAtiva?.id || collections[0]?.id || "";

  const acoesCollection = useCollectionActions({
    onColecoesMudaram,
    onCollectionIdChange: setCollectionId,
    onError: (msg) => setError(msg || null),
  });

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || isSubmitting || !token) return;
    setIsSubmitting(true);
    setError(null);
    setResult(null);
    try {
      const response = await uploadDocument(token, {
        file,
        domain,
        collectionId: collectionSelecionada || undefined,
      });
      setResult(response);
      setFile(null);
      onIngerido();
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao enviar o documento.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleFileChange(f: File | null) {
    setFile(f);
    if (f) setError(null);
  }

  return {
    file,
    domain,
    setDomain,
    setCollectionId,
    isSubmitting,
    result,
    error,
    setError,
    collectionSelecionada,
    selectedPurpose: collectionSelecionadaObj?.purpose || "chat",
    handleSubmit,
    handleFileChange,
    ...acoesCollection,
  };
}
