"use client";

// MVP: página administrativa (fora da navegação pública, sem autenticação)
// para gerenciar os modelos locais do Ollama e parâmetros de execução em runtime.
import { useCallback, useEffect, useState } from "react";

import { LocalModelsTable } from "@/components/admin/LocalModelsTable";
import { PullModelForm } from "@/components/admin/PullModelForm";
import { RuntimeSettingsForm } from "@/components/admin/RuntimeSettingsForm";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
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
    <div className="mx-auto max-w-4xl px-4 py-12 sm:py-16">
      <div className="border-b border-slate-200 pb-5">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Administração Geral</h1>
        <p className="mt-2 text-sm text-slate-600">
          Painel de controle administrativo para gerenciamento de modelos LLM locais (Ollama) e parâmetros de execução em runtime.
        </p>
      </div>

      <div className="mt-6">
        <Tabs defaultValue="modelos">
          <TabsList>
            <TabsTrigger value="modelos">🤖 Modelos Locais</TabsTrigger>
            <TabsTrigger value="parametros">⚙️ Parâmetros de Execução</TabsTrigger>
          </TabsList>

          <TabsContent value="modelos">
            <div className="space-y-6">
              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
                <h2 className="text-lg font-semibold text-slate-900">Modelos baixados</h2>
                {activeModel !== null && (
                  <p className="mt-1 text-sm text-slate-600">
                    Modelo ativo no chat: <strong className="font-mono text-slate-900">{activeModel || "Nenhum"}</strong>
                  </p>
                )}
                <div className="mt-4">
                  {modelos === null ? (
                    <p className="text-sm text-slate-500">Carregando modelos...</p>
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

              <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
                <h2 className="text-lg font-semibold text-slate-900">Baixar um modelo novo</h2>
                <p className="mt-1 text-xs sm:text-sm text-slate-600">
                  Nome da biblioteca do Ollama (ex.: <code className="rounded bg-slate-100 px-1 py-0.5 font-mono">llama3.1:8b</code>) ou um GGUF do Hugging Face
                  (ex.: <code className="rounded bg-slate-100 px-1 py-0.5 font-mono">hf.co/usuario/repo:Q4_K_M</code>).
                </p>
                <div className="mt-4">
                  <PullModelForm onPulled={carregarModelos} />
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="parametros">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-xs">
              <h2 className="text-lg font-semibold text-slate-900">Parâmetros de execução</h2>
              <p className="mt-1 text-xs sm:text-sm text-slate-600">
                Ajustáveis em runtime, só em memória — resetam a cada restart do backend.
              </p>
              <div className="mt-4">
                <RuntimeSettingsForm
                  onError={(message) => showToast(message, "error")}
                  onSuccess={(message) => showToast(message, "success")}
                />
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
