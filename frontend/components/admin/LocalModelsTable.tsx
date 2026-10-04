"use client";

import { useState } from "react";

import { LocalModelsApiError, activateModel, pullModel } from "@/lib/api/localModels";
import type { LocalModel } from "@/lib/types/localModels";
import { Tooltip } from "@/components/ui/Tooltip";
import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";

interface PresetLocalModel {
  tag: string;
  name: string;
  provider: string;
  sizeEstimate: string;
  description: string;
}

const POPULAR_LOCAL_PRESETS: PresetLocalModel[] = [
  {
    tag: "llama3.1:8b",
    name: "Llama 3.1 8B",
    provider: "Meta AI",
    sizeEstimate: "4.7 GB",
    description: "Excelente equilíbrio entre desempenho, velocidade e inteligência geral.",
  },
  {
    tag: "qwen2.5:7b",
    name: "Qwen 2.5 7B",
    provider: "Alibaba Cloud",
    sizeEstimate: "4.7 GB",
    description: "Alta precisão em instruções complexas, raciocínio e suporte a código.",
  },
  {
    tag: "deepseek-r1:7b",
    name: "DeepSeek R1 7B",
    provider: "DeepSeek",
    sizeEstimate: "4.7 GB",
    description: "Especializado em raciocínio encadeado (CoT) e resolução de problemas.",
  },
  {
    tag: "mistral:7b",
    name: "Mistral 7B",
    provider: "Mistral AI",
    sizeEstimate: "4.1 GB",
    description: "Modelo compacto e muito rápido para conversação e RAG.",
  },
  {
    tag: "gemma2:9b",
    name: "Gemma 2 9B",
    provider: "Google",
    sizeEstimate: "5.4 GB",
    description: "Arquitetura avançada desenvolvida pelo Google para execução local.",
  },
  {
    tag: "phi3:mini",
    name: "Phi-3 Mini 3.8B",
    provider: "Microsoft",
    sizeEstimate: "2.3 GB",
    description: "Ultra-leve e otimizado para execução rápida com baixo uso de RAM.",
  },
];

function formatarTamanho(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  return `${gb.toFixed(1)} GB`;
}

// Envolve cada card com o tooltip de características do modelo (hover),
// centralizando a chamada do hook para não repeti-la em cada `.map`.
function CardComCaracteristicas({ tag, children }: { tag: string; children: React.ReactElement }) {
  const { data, loading, error, refresh } = useModelCharacteristics("ollama", tag);
  return (
    <Tooltip
      content={`Características de ${tag}`}
      trigger={children}
      renderContent={() => (
        <ModelCharacteristicsPanel
          data={data}
          loading={loading}
          error={error}
          onRefresh={refresh}
        />
      )}
    />
  );
}

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffDias = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDias <= 0) return "hoje";
  if (diffDias === 1) return "há 1 dia";
  return `há ${diffDias} dias`;
}

export interface LocalModelsTableProps {
  models: LocalModel[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function LocalModelsTable({ models, onChanged, onError, onSuccess }: LocalModelsTableProps) {
  const [processandoTag, setProcessandoTag] = useState<string | null>(null);
  const [baixandoPreset, setBaixandoPreset] = useState<string | null>(null);

  const activeModel = models.find((m) => m.is_active);

  async function handleAtivar(modelo: LocalModel) {
    setProcessandoTag(modelo.name);
    try {
      await activateModel(modelo.name);
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

  async function handleBaixarPreset(tag: string) {
    setBaixandoPreset(tag);
    try {
      onSuccess(`Iniciando download do modelo "${tag}"...`);
      await pullModel(tag);
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

  return (
    <div className="space-y-8">
      {/* Banner Destaque do Modelo Local Ativo */}
      <div className="rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white text-2xl shadow-sm">
            🤖
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">
                Modelo Local Ativo (Ollama)
              </span>
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <h2 className="text-lg font-bold text-slate-900 font-mono mt-0.5">
              {activeModel ? activeModel.name : "Nenhum selecionado"}
            </h2>
          </div>
        </div>

        <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-emerald-700 border border-emerald-200 shadow-2xs">
          <span>{activeModel ? "✓ Em Execução no Ollama" : "⚠️ Nenhum ativo"}</span>
        </div>
      </div>

      {/* Seção 1: Grid de Modelos Locais Instalados */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>💻</span> Modelos Locais Instalados
          </h3>
          <span className="text-xs text-slate-500">
            {models.length} modelo(s) armazenados no servidor Ollama
          </span>
        </div>

        {models.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-2xl">
              📦
            </div>
            <h4 className="mt-3 text-sm font-bold text-slate-800">
              Nenhum modelo local baixado ainda
            </h4>
            <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
              Escolha um dos modelos recomendados abaixo ou informe a tag de um modelo para realizar
              o download no servidor.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {models.map((modelo) => {
              const isSelected = modelo.is_active;
              const isActivating = processandoTag === modelo.name;

              return (
                <CardComCaracteristicas key={modelo.name} tag={modelo.name}>
                  <div
                    className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
                      isSelected
                        ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                        : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                          Ollama Local
                        </span>
                        {isSelected && (
                          <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800 flex items-center gap-1">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            Ativo
                          </span>
                        )}
                      </div>

                      <h4
                        className="mt-2 font-bold text-slate-900 text-sm font-mono truncate"
                        title={modelo.name}
                      >
                        {modelo.name}
                      </h4>

                      <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                        <span className="font-mono font-semibold text-slate-700">
                          {formatarTamanho(modelo.size_bytes)}
                        </span>
                        <span>•</span>
                        <span title={modelo.modified_at}>
                          {formatarDataRelativa(modelo.modified_at)}
                        </span>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100">
                      {!isSelected && (
                        <button
                          type="button"
                          onClick={() => handleAtivar(modelo)}
                          disabled={isActivating}
                          className="w-full rounded-lg bg-blue-600 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer shadow-2xs"
                        >
                          {isActivating ? "Ativando..." : "Ativar"}
                        </button>
                      )}
                      {isSelected && (
                        <div className="w-full text-center py-2 text-xs font-bold text-slate-400 bg-slate-100 rounded-lg cursor-default">
                          Modelo Ativo
                        </div>
                      )}
                    </div>
                  </div>
                </CardComCaracteristicas>
              );
            })}
          </div>
        )}
      </div>

      {/* Seção 2: Modelos Recomendados do Ollama */}
      <div className="space-y-3 pt-4 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>⭐</span> Modelos Recomendados para Execução Local
          </h3>
          <span className="text-xs text-slate-500">Populares na biblioteca Ollama</span>
        </div>

        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {POPULAR_LOCAL_PRESETS.map((preset) => {
            const instalado = models.find((m) => m.name === preset.tag);
            const isSelected = instalado?.is_active ?? false;
            const isDownloading = baixandoPreset === preset.tag;
            const isActivating = processandoTag === preset.tag;

            return (
              <CardComCaracteristicas key={preset.tag} tag={preset.tag}>
                <div
                  className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
                    isSelected
                      ? "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs"
                      : instalado
                        ? "border-slate-300 bg-slate-50/50"
                        : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
                  }`}
                >
                  <div>
                    <div className="flex items-center justify-between gap-2">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                        {preset.provider}
                      </span>
                      {isSelected && (
                        <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                          Ativo
                        </span>
                      )}
                      {!isSelected && instalado && (
                        <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
                          Instalado
                        </span>
                      )}
                    </div>

                    <h4 className="mt-2 font-bold text-slate-900 text-sm">{preset.name}</h4>
                    <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">
                      {preset.description}
                    </p>

                    <div className="mt-2 flex items-center justify-between text-[10px]">
                      <code className="font-mono text-slate-400">ollama pull {preset.tag}</code>
                      <span className="font-semibold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                        ~{preset.sizeEstimate}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100">
                    {instalado ? (
                      <button
                        type="button"
                        disabled={isSelected || isActivating}
                        onClick={() => handleAtivar(instalado)}
                        className={`w-full rounded-lg py-2 text-xs font-bold transition-colors ${
                          isSelected
                            ? "bg-slate-100 text-slate-400 cursor-default"
                            : "bg-blue-600 text-white hover:bg-blue-700 shadow-2xs cursor-pointer"
                        }`}
                      >
                        {isActivating
                          ? "Ativando..."
                          : isSelected
                            ? "Modelo Ativo"
                            : "Ativar Modelo"}
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={isDownloading}
                        onClick={() => handleBaixarPreset(preset.tag)}
                        className="w-full rounded-lg bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors cursor-pointer shadow-2xs"
                      >
                        {isDownloading ? "Baixando..." : "Baixar Modelo"}
                      </button>
                    )}
                  </div>
                </div>
              </CardComCaracteristicas>
            );
          })}
        </div>
      </div>
    </div>
  );
}
