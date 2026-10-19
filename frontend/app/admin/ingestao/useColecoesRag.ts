import { useCallback, useEffect, useState } from "react";

import type { ToastVariant } from "@/components/ui/Toast";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { RagApiError, listCollections } from "@/lib/api/rag";
import type { RagCollection } from "@/lib/types/rag";

/**
 * Lista de collections do RAG, carregada ao montar; `carregarColecoes` recarrega
 * sob demanda. `showToast` deve ser estável (vem de `useToast`).
 */
export function useColecoesRag(showToast: (message: string, variant: ToastVariant) => void) {
  const token = useAuthStore((s) => s.token);
  const [collections, setCollections] = useState<RagCollection[]>([]);

  const carregarColecoes = useCallback(async (): Promise<RagCollection[]> => {
    if (!token) return [];
    try {
      const novalista = await listCollections(token);
      setCollections(novalista);
      return novalista;
    } catch (err) {
      showToast(
        err instanceof RagApiError ? err.message : "Erro inesperado ao carregar as collections.",
        "error",
      );
      return [];
    }
  }, [showToast, token]);

  useEffect(() => {
    // Falso positivo: `carregarColecoes` so toca estado depois de
    // `await listCollections` (funcao `async` importada), logo nao ha setState
    // sincrono aqui. A regra nao resolve a assincronia da chamada e assume o
    // pior caso.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void carregarColecoes();
  }, [carregarColecoes]);

  return { collections, carregarColecoes };
}
