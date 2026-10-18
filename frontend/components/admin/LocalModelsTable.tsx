"use client";

import { useState } from "react";

import { LocalModelsApiError, activateModel, deleteModel, pullModel } from "@/lib/api/localModels";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
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

function LocalModelCard({
  modelo,
  isActivating,
  isDeleting,
  onAtivar,
  onDesinstalar,
}: {
  modelo: LocalModel;
  isActivating: boolean;
  isDeleting: boolean;
  onAtivar: (m: LocalModel) => void;
  onDesinstalar: (m: LocalModel) => void;
}) {
  const isSelected = modelo.is_active;
  return (
    <CardComCaracteristicas tag={modelo.name}>
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
            <span title={modelo.modified_at}>{formatarDataRelativa(modelo.modified_at)}</span>
          </div>
        </div>
        <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col gap-2">
          {!isSelected && (
            <button
              type="button"
              onClick={() => onAtivar(modelo)}
              disabled={isActivating || isDeleting}
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
          <button
            type="button"
            onClick={() => onDesinstalar(modelo)}
            disabled={isDeleting || isActivating || isSelected}
            title={
              isSelected ? "Ative outro modelo antes de desinstalar este" : "Desinstalar modelo"
            }
            className="w-full rounded-lg border border-red-200 py-2 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
          >
            {isDeleting ? "Removendo..." : "🗑 Desinstalar"}
          </button>
        </div>
      </div>
    </CardComCaracteristicas>
  );
}

function LocalPresetCard({
  preset,
  instalado,
  isDownloading,
  isActivating,
  onAtivar,
  onBaixar,
}: {
  preset: PresetLocalModel;
  instalado: LocalModel | undefined;
  isDownloading: boolean;
  isActivating: boolean;
  onAtivar: (m: LocalModel) => void;
  onBaixar: (tag: string) => void;
}) {
  const isSelected = instalado?.is_active ?? false;
  return (
    <CardComCaracteristicas tag={preset.tag}>
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
          <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{preset.description}</p>
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
              onClick={() => onAtivar(instalado)}
              className={`w-full rounded-lg py-2 text-xs font-bold transition-colors ${
                isSelected
                  ? "bg-slate-100 text-slate-400 cursor-default"
                  : "bg-blue-600 text-white hover:bg-blue-700 shadow-2xs cursor-pointer"
              }`}
            >
              {isActivating ? "Ativando..." : isSelected ? "Modelo Ativo" : "Ativar Modelo"}
            </button>
          ) : (
            <button
              type="button"
              disabled={isDownloading}
              onClick={() => onBaixar(preset.tag)}
              className="w-full rounded-lg bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors cursor-pointer shadow-2xs"
            >
              {isDownloading ? "Baixando..." : "Baixar Modelo"}
            </button>
          )}
        </div>
      </div>
    </CardComCaracteristicas>
  );
}

export interface LocalModelsTableProps {
  models: LocalModel[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

export function LocalModelsTable({ models, onChanged, onError, onSuccess }: LocalModelsTableProps) {
  const token = useAuthStore((s) => s.token);
  const [processandoTag, setProcessandoTag] = useState<string | null>(null);
  const [baixandoPreset, setBaixandoPreset] = useState<string | null>(null);
  const [deletandoTag, setDeletandoTag] = useState<string | null>(null);
  const [confirmarDelete, setConfirmarDelete] = useState<LocalModel | null>(null);

  const activeModel = models.find((m) => m.is_active);

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

  return (
    <div className="space-y-8">
      {/* Modal de confirmação de desinstalação */}
      {confirmarDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl max-w-sm w-full mx-4">
            <h3 className="text-base font-bold text-slate-900">🗑 Desinstalar modelo?</h3>
            <p className="mt-2 text-sm text-slate-600">
              Tem certeza que deseja remover{" "}
              <span className="font-mono font-bold text-slate-900">{confirmarDelete.name}</span> (
              {formatarTamanho(confirmarDelete.size_bytes)}) do Ollama? Esta ação não pode ser
              desfeita.
            </p>
            <div className="mt-5 flex gap-3">
              <button
                type="button"
                onClick={() => setConfirmarDelete(null)}
                className="flex-1 rounded-lg border border-slate-200 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={() => handleDesinstalar(confirmarDelete)}
                className="flex-1 rounded-lg bg-red-600 py-2 text-xs font-bold text-white hover:bg-red-700 transition-colors cursor-pointer"
              >
                Sim, remover
              </button>
            </div>
          </div>
        </div>
      )}
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
            {models.map((modelo) => (
              <LocalModelCard
                key={modelo.name}
                modelo={modelo}
                isActivating={processandoTag === modelo.name}
                isDeleting={deletandoTag === modelo.name}
                onAtivar={handleAtivar}
                onDesinstalar={(m) => setConfirmarDelete(m)}
              />
            ))}
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
          {POPULAR_LOCAL_PRESETS.map((preset) => (
            <LocalPresetCard
              key={preset.tag}
              preset={preset}
              instalado={models.find((m) => m.name === preset.tag)}
              isDownloading={baixandoPreset === preset.tag}
              isActivating={processandoTag === preset.tag}
              onAtivar={handleAtivar}
              onBaixar={handleBaixarPreset}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
