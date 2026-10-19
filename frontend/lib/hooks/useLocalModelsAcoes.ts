"use client";

import { useState } from "react";

import { LocalModelsApiError, activateModel, deleteModel, pullModel } from "@/lib/api/localModels";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { LocalModel } from "@/lib/types/localModels";

interface AcoesDeps {
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

/** Estado e ações (ativar, desinstalar, baixar preset) da tela de modelos locais. */
export function useLocalModelsAcoes({ onChanged, onError, onSuccess }: AcoesDeps) {
  const token = useAuthStore((s) => s.token);
  const [processandoTag, setProcessandoTag] = useState<string | null>(null);
  const [baixandoPreset, setBaixandoPreset] = useState<string | null>(null);
  const [deletandoTag, setDeletandoTag] = useState<string | null>(null);
  const [confirmarDelete, setConfirmarDelete] = useState<LocalModel | null>(null);

  async function handleAtivar(modelo: LocalModel) {
    if (!token) return;
    setProcessandoTag(modelo.name);
    try {
      await activateModel(token, modelo.name);
      onSuccess(`"${modelo.name}" agora é o modelo ativo no chat.`);
      onChanged();
    } catch (err) {
      onError(
        err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao ativar o modelo.",
      );
    } finally {
      setProcessandoTag(null);
    }
  }

  async function handleDesinstalar(modelo: LocalModel) {
    if (!token) return;
    setConfirmarDelete(null);
    setDeletandoTag(modelo.name);
    try {
      await deleteModel(token, modelo.name);
      onSuccess(`Modelo "${modelo.name}" removido com sucesso.`);
      onChanged();
    } catch (err) {
      onError(
        err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao remover o modelo.",
      );
    } finally {
      setDeletandoTag(null);
    }
  }

  async function handleBaixarPreset(tag: string) {
    if (!token) return;
    setBaixandoPreset(tag);
    try {
      onSuccess(`Iniciando download do modelo "${tag}"...`);
      await pullModel(token, tag);
      onSuccess(`Modelo "${tag}" baixado com sucesso!`);
      onChanged();
    } catch (err) {
      onError(
        err instanceof LocalModelsApiError ? err.message : "Erro ao baixar modelo recomendado.",
      );
    } finally {
      setBaixandoPreset(null);
    }
  }

  return {
    processandoTag,
    baixandoPreset,
    deletandoTag,
    confirmarDelete,
    setConfirmarDelete,
    handleAtivar,
    handleDesinstalar,
    handleBaixarPreset,
  };
}
