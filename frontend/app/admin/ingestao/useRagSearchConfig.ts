import { useEffect, useState } from "react";

import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";

interface Params {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

/** Carrega e alterna a regra de busca do RAG (fallback sem filtro de domínio). */
export function useRagSearchConfig({ onError, onSuccess }: Params) {
  const token = useAuthStore((s) => s.token);
  const [ragFallback, setRagFallback] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!token) return;
    let cancelado = false;
    async function carregar() {
      try {
        const atual = await getRuntimeSettings(token!);
        if (!cancelado) setRagFallback(atual.rag_search_domain_fallback);
      } catch (err) {
        if (!cancelado) {
          onError(err instanceof Error ? err.message : "Erro ao carregar configurações de busca.");
        }
      } finally {
        if (!cancelado) setCarregando(false);
      }
    }
    carregar();
    return () => {
      cancelado = true;
    };
    // Roda só uma vez ao montar — incluir `onError` (recriada a cada render
    // do pai) reexecutaria a busca a cada render, não só no mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleToggle(checked: boolean) {
    if (!token) return;
    setSalvando(true);
    setRagFallback(checked);
    try {
      await updateRuntimeSettings(token, { rag_search_domain_fallback: checked });
      onSuccess("Regra de busca do RAG atualizada.");
    } catch (err) {
      setRagFallback(!checked);
      onError(err instanceof Error ? err.message : "Erro ao atualizar regra de busca.");
    } finally {
      setSalvando(false);
    }
  }

  return { ragFallback, carregando, salvando, handleToggle };
}
