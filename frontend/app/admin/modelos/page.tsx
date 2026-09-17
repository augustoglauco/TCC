"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para gerenciar os modelos locais do Ollama — listar, ativar em runtime e
// baixar (biblioteca do Ollama ou GGUF do Hugging Face). Não substitui nem
// antecipa a Fase 10 (escolha do LOCAL_MODEL_NAME de produção via
// benchmark offline, ver docs/ROADMAP.md). Ver
// docs/superpowers/specs/2026-09-16-local-model-manager-design.md.
import { useCallback, useEffect, useState } from "react";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import { PullModelForm } from "@/components/admin/PullModelForm";
import { RuntimeSettingsForm } from "@/components/admin/RuntimeSettingsForm";
import { ToastStack, useToast } from "@/components/ui/Toast";
import { LocalModelsApiError, listLocalModels } from "@/lib/api/localModels";
import type { LocalModel } from "@/lib/types/localModels";

export default function ModelosPage() {
  const [modelos, setModelos] = useState<LocalModel[] | null>(null);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const { toasts, showToast, dismissToast } = useToast();

  const carregarModelos = useCallback(async () => {
    try {
      const resposta = await listLocalModels();
      setModelos(resposta.models);
      setActiveModel(resposta.active_model);
    } catch (err) {
      showToast(
        err instanceof LocalModelsApiError ? err.message : "Erro inesperado ao carregar os modelos.",
        "error",
      );
      setModelos([]);
    }
  }, [showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarModelos();
  }, [carregarModelos]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <h1 className="text-2xl font-semibold text-gray-900">Modelos locais (Ollama)</h1>
      <p className="mt-2 text-gray-600">
        Página interna, sem impacto na navegação pública do site. Ferramenta de teste — não
        substitui a escolha formal de modelo de produção (Fase 10 do roadmap).
      </p>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Modelos baixados</h2>
        {activeModel !== null && (
          <p className="mt-1 text-sm text-gray-600">
            Modelo ativo no chat: <strong>{activeModel || "Nenhum"}</strong>
          </p>
        )}
        <div className="mt-4">
          {modelos === null ? (
            <p className="text-sm text-gray-600">Carregando...</p>
          ) : (
            <LocalModelsTable
              models={modelos}
              onChanged={carregarModelos}
              onError={(message) => showToast(message, "error")}
              onSuccess={(message) => showToast(message, "success")}
            />
          )}
        </div>
      </div>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Baixar um modelo novo</h2>
        <p className="mt-1 text-sm text-gray-600">
          Nome da biblioteca do Ollama (ex.: <code>llama3.1:8b</code>) ou um GGUF do Hugging Face
          (ex.: <code>hf.co/usuario/repo:Q4_K_M</code>).
        </p>
        <div className="mt-4">
          <PullModelForm onPulled={carregarModelos} />
        </div>
      </div>

      <div className="mt-8 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-medium text-gray-900">Parâmetros de execução</h2>
        <p className="mt-1 text-sm text-gray-600">
          Ajustáveis em runtime, só em memória — resetam a cada restart do backend.
        </p>
        <div className="mt-4">
          <RuntimeSettingsForm
            onError={(message) => showToast(message, "error")}
            onSuccess={(message) => showToast(message, "success")}
          />
        </div>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
