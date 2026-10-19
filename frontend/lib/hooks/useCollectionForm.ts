"use client";

import { useState } from "react";

import {
  VALORES_INICIAIS,
  chunkingInvalido,
  modeloDeEmbedding,
  montarPayload,
  type CollectionFormValores,
} from "@/components/admin/collectionFormPayload";
import { RagApiError, activateCollection, createCollection } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { PayloadIndex, RagCollection } from "@/lib/types/rag";

export function useCollectionForm(onCreated: (collection: RagCollection) => void) {
  const token = useAuthStore((s) => s.token);
  const [valores, setValores] = useState<CollectionFormValores>(VALORES_INICIAIS);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const embeddingModel = modeloDeEmbedding(valores);
  const invalido = chunkingInvalido(valores);

  function set<K extends keyof CollectionFormValores>(campo: K, valor: CollectionFormValores[K]) {
    setValores((atual) => ({ ...atual, [campo]: valor }));
  }

  function resetar() {
    setValores(VALORES_INICIAIS);
    setError(null);
  }

  function atualizarPayloadIndex(indice: number, campo: Partial<PayloadIndex>) {
    setValores((atual) => ({
      ...atual,
      payloadIndexes: atual.payloadIndexes.map((item, i) =>
        i === indice ? { ...item, ...campo } : item,
      ),
    }));
  }

  function removerPayloadIndex(indice: number) {
    setValores((atual) => ({
      ...atual,
      payloadIndexes: atual.payloadIndexes.filter((_, i) => i !== indice),
    }));
  }

  function adicionarPayloadIndex() {
    setValores((atual) => ({
      ...atual,
      payloadIndexes: [...atual.payloadIndexes, { field: "", schema_type: "keyword" }],
    }));
  }

  /** Cria a collection; devolve true se concluiu (para o modal fechar). */
  async function enviar(): Promise<boolean> {
    if (isSubmitting || invalido || !embeddingModel || !token) return false;

    setIsSubmitting(true);
    setError(null);
    try {
      const collection = await createCollection(token, montarPayload(valores));
      if (valores.ativarAposCriar) {
        try {
          await activateCollection(token, collection.id);
          collection.is_active = true;
        } catch (err) {
          // Ativação não crítica pós-criação
          console.warn("Não foi possível ativar a collection após criar:", err);
        }
      }
      onCreated(collection);
      resetar();
      return true;
    } catch (err) {
      setError(err instanceof RagApiError ? err.message : "Erro inesperado ao criar a collection.");
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }

  return {
    valores,
    set,
    error,
    isSubmitting,
    embeddingModel,
    chunkingInvalido: invalido,
    resetar,
    enviar,
    atualizarPayloadIndex,
    removerPayloadIndex,
    adicionarPayloadIndex,
  };
}
