"use client";

import { useEffect, useState } from "react";
import { getRuntimeSettings, updateRuntimeSettings } from "@/lib/api/runtimeSettings";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

const STORAGE_KEY = "openrouter_model_history";
const MODELO_PADRAO = "openai/gpt-4o-mini";

function lerHistorico(): string[] {
  const salvo = localStorage.getItem(STORAGE_KEY);
  if (!salvo) return [];
  try {
    return JSON.parse(salvo);
  } catch {
    return [];
  }
}

function salvarHistorico(lista: string[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(lista));
}

interface Callbacks {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

// Estado e ações do card de modelo externo (OpenRouter): modelo ativo vindo do
// backend, histórico no localStorage e ativação de uma tag.
export function useOpenRouterModelo({ onError, onSuccess }: Callbacks) {
  const token = useAuthStore((s) => s.token);
  const [activeModel, setActiveModel] = useState<string>("");
  const [historyModels, setHistoryModels] = useState<string[]>([]);
  const [customInput, setCustomInput] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [activatingTag, setActivatingTag] = useState<string | null>(null);

  // Carrega modelo ativo do backend e histórico do localStorage
  useEffect(() => {
    let cancelado = false;

    async function init() {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const settings = await getRuntimeSettings(token);
        if (cancelado) return;
        const currentModel = settings.external_model_name || MODELO_PADRAO;
        setActiveModel(currentModel);

        let list = lerHistorico();
        if (!list.includes(currentModel)) list = [currentModel, ...list];
        setHistoryModels(list);
        salvarHistorico(list);
      } catch (err) {
        if (!cancelado) {
          onError(err instanceof Error ? err.message : "Erro ao carregar modelo externo.");
        }
      } finally {
        if (!cancelado) setLoading(false);
      }
    }

    init();
    return () => {
      cancelado = true;
    };
  }, [onError, token]);

  // Função central para ativar modelo e guardar no histórico
  const handleActivateModel = async (modelTag: string) => {
    const tag = modelTag.trim();
    if (!tag || activatingTag || !token) return;

    setActivatingTag(tag);
    try {
      await updateRuntimeSettings(token, { external_model_name: tag });
      setActiveModel(tag);
      setHistoryModels((prev) => {
        const updated = [tag, ...prev.filter((m) => m !== tag)];
        salvarHistorico(updated);
        return updated;
      });
      onSuccess(`Modelo externo ativado com sucesso: ${tag}`);
      setCustomInput("");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Falha ao ativar modelo no OpenRouter.");
    } finally {
      setActivatingTag(null);
    }
  };

  const handleRemoveFromHistory = (tag: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setHistoryModels((prev) => {
      const updated = prev.filter((m) => m !== tag);
      salvarHistorico(updated);
      return updated;
    });
  };

  return {
    activeModel,
    historyModels,
    customInput,
    setCustomInput,
    loading,
    activatingTag,
    handleActivateModel,
    handleRemoveFromHistory,
  };
}
