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

  const totalBytes = modelos?.reduce((acc, m) => acc + (m.size_bytes || 0), 0) ?? 0;
  const totalGb = (totalBytes / 1024 ** 3).toFixed(1);

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12">
      {/* Header com badge de contexto */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-6">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 shadow-2xs mb-2">
            <span>⚙️ Painel de Controle Admin</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Administração Geral
          </h1>
          <p className="mt-1.5 text-xs sm:text-sm text-slate-600 max-w-2xl">
            Gerenciamento de modelos LLM locais (Ollama), downloads do Hugging Face e parâmetros de inferência em tempo de execução.
          </p>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="mt-6 grid grid-cols-1 gap-3.5 sm:grid-cols-3">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs flex items-center gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-600 text-xl font-bold">
            🤖
          </div>
          <div className="min-w-0">
            <span className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Modelo Ativo
            </span>
            <span className="block text-sm font-bold text-slate-900 truncate" title={activeModel || "Nenhum"}>
              {activeModel ? activeModel : "Nenhum selecionado"}
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs flex items-center gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 text-xl font-bold">
            📦
          </div>
          <div>
            <span className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Modelos Baixados
            </span>
            <span className="block text-sm font-bold text-slate-900">
              {modelos === null ? "..." : `${modelos.length} modelo(s) (${totalGb} GB)`}
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-4 shadow-xs flex items-center gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 text-xl font-bold">
            ⚡
          </div>
          <div>
            <span className="block text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
              Status Runtime
            </span>
            <span className="block text-sm font-bold text-emerald-700 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              Operacional (Ollama)
            </span>
          </div>
        </div>
      </div>

      {/* Conteúdo com Abas */}
      <div className="mt-8">
        <Tabs defaultValue="modelos">
          <TabsList className="p-1 bg-slate-100 rounded-xl border border-slate-200/80 inline-flex">
            <TabsTrigger value="modelos">🤖 Modelos Locais</TabsTrigger>
            <TabsTrigger value="parametros">⚙️ Parâmetros de Execução</TabsTrigger>
          </TabsList>

          <TabsContent value="modelos">
            <div className="space-y-6">
              {/* Card 1: Modelos Baixados */}
              <div className="rounded-2xl border border-slate-200/80 bg-white p-5 sm:p-6 shadow-xs space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-4">
                  <div>
                    <h2 className="text-base sm:text-lg font-bold text-slate-900">Modelos Locais Instalados</h2>
                    <p className="text-xs text-slate-500">Modelos armazenados na biblioteca do Ollama e prontos para uso</p>
                  </div>
                  {activeModel !== null && (
                    <div className="inline-flex items-center gap-2 rounded-xl bg-slate-100 px-3 py-1.5 text-xs text-slate-700">
                      <span>Modelo ativo no chat:</span>
                      <strong className="font-mono text-slate-900">{activeModel || "Nenhum"}</strong>
                    </div>
                  )}
                </div>

                <div>
                  {modelos === null ? (
                    <div className="flex items-center justify-center py-8 text-xs text-slate-500">
                      Carregando repositório de modelos...
                    </div>
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

              {/* Card 2: Baixar Novo Modelo */}
              <div className="rounded-2xl border border-slate-200/80 bg-white p-5 sm:p-6 shadow-xs space-y-4">
                <div className="border-b border-slate-100 pb-4">
                  <h2 className="text-base sm:text-lg font-bold text-slate-900">Baixar Novo Modelo LLM</h2>
                  <p className="mt-1 text-xs text-slate-500">
                    Insira a tag da biblioteca do Ollama (ex.: <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-slate-800">llama3.1:8b</code>) ou URL GGUF do Hugging Face.
                  </p>
                </div>
                <PullModelForm onPulled={carregarModelos} />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="parametros">
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 sm:p-6 shadow-xs space-y-4">
              <div className="border-b border-slate-100 pb-4">
                <h2 className="text-base sm:text-lg font-bold text-slate-900">Parâmetros de Execução em Runtime</h2>
                <p className="mt-1 text-xs text-slate-500">
                  Configurações de inferência, timeouts e mecanismo de roteamento mantidos em memória no backend.
                </p>
              </div>
              <RuntimeSettingsForm
                onError={(message) => showToast(message, "error")}
                onSuccess={(message) => showToast(message, "success")}
              />
            </div>
          </TabsContent>
        </Tabs>
      </div>

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
