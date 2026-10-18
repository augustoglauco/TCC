import { useState } from "react";
import { RagApiError, activateCollection, createCollection } from "@/lib/api/rag";
import type { CollectionPurpose, RagCollection } from "@/lib/types/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

interface UseCollectionActionsParams {
  onColecoesMudaram: () => Promise<RagCollection[]>;
  onCollectionIdChange: (id: string) => void;
  onError: (msg: string) => void;
}

export function useCollectionActions({
  onColecoesMudaram,
  onCollectionIdChange,
  onError,
}: UseCollectionActionsParams) {
  const token = useAuthStore((s) => s.token);
  const [criandoCollection, setCriandoCollection] = useState(false);
  const [modalCriarAberto, setModalCriarAberto] = useState(false);

  async function criarCollectionRapida(purpose: CollectionPurpose) {
    if (!token) return;
    setCriandoCollection(true);
    onError("");
    const nomePadrao =
      purpose === "mcp_b2b" ? "docs_mcp_b2b" : purpose === "admin" ? "docs_admin" : "docs_chat";

    try {
      const novaCol = await createCollection(token, {
        name: nomePadrao,
        purpose,
        embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
        distance_metric: "cosine",
        chunk_size: 800,
        chunk_overlap: 100,
        hnsw: {
          m: 16,
          ef_construct: 100,
          full_scan_threshold: 10000,
          max_indexing_threads: 0,
          on_disk: false,
          payload_m: null,
        },
        quantization: { type: "none" },
        payload_indexes: [
          { field: "domain", schema_type: "keyword" },
          { field: "document_id", schema_type: "keyword" },
        ],
      });
      try {
        await activateCollection(token, novaCol.id);
      } catch {
        // Ativação não impeditiva
      }
      await onColecoesMudaram();
      onCollectionIdChange(novaCol.id);
    } catch (err) {
      // Se a coleção já foi criada anteriormente, recarrega do banco e seleciona automaticamente!
      const novalista = await onColecoesMudaram();
      const colExistente = novalista?.find((c) => c.name === nomePadrao || c.purpose === purpose);
      if (colExistente) {
        onCollectionIdChange(colExistente.id);
        onError("");
      } else {
        onError(err instanceof RagApiError ? err.message : "Erro ao criar a collection.");
      }
    } finally {
      setCriandoCollection(false);
    }
  }

  function handleSelectCollectionChange(val: string) {
    if (val === "__create_mcp_b2b__") {
      criarCollectionRapida("mcp_b2b");
    } else if (val === "__create_admin__") {
      criarCollectionRapida("admin");
    } else if (val === "__create_chat__") {
      criarCollectionRapida("chat");
    } else if (val === "__open_modal__") {
      setModalCriarAberto(true);
    } else {
      onCollectionIdChange(val);
    }
  }

  return {
    criandoCollection,
    modalCriarAberto,
    setModalCriarAberto,
    criarCollectionRapida,
    handleSelectCollectionChange,
  };
}
