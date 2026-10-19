"use client";

import { Tooltip } from "@/components/ui/Tooltip";
import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";
import type { LocalModel } from "@/lib/types/localModels";

export interface PresetLocalModel {
  tag: string;
  name: string;
  provider: string;
  sizeEstimate: string;
  description: string;
}

export const POPULAR_LOCAL_PRESETS: PresetLocalModel[] = [
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

export function formatarTamanho(bytes: number): string {
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

function SeloAtivoInstalado({
  instalado,
  isSelected,
}: {
  instalado: boolean;
  isSelected: boolean;
}) {
  if (isSelected) {
    return (
      <span className="rounded bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
        Ativo
      </span>
    );
  }
  if (!instalado) return null;
  return (
    <span className="rounded bg-blue-100 px-2 py-0.5 text-[10px] font-bold text-blue-800">
      Instalado
    </span>
  );
}

function AcoesModeloInstalado({
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
    <div className="mt-4 pt-3 border-t border-slate-100 flex flex-col gap-2">
      {isSelected ? (
        <div className="w-full text-center py-2 text-xs font-bold text-slate-400 bg-slate-100 rounded-lg cursor-default">
          Modelo Ativo
        </div>
      ) : (
        <button
          type="button"
          onClick={() => onAtivar(modelo)}
          disabled={isActivating || isDeleting}
          className="w-full rounded-lg bg-blue-600 py-2 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer shadow-2xs"
        >
          {isActivating ? "Ativando..." : "Ativar"}
        </button>
      )}
      <button
        type="button"
        onClick={() => onDesinstalar(modelo)}
        disabled={isDeleting || isActivating || isSelected}
        title={isSelected ? "Ative outro modelo antes de desinstalar este" : "Desinstalar modelo"}
        className="w-full rounded-lg border border-red-200 py-2 text-xs font-bold text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer"
      >
        {isDeleting ? "Removendo..." : "🗑 Desinstalar"}
      </button>
    </div>
  );
}

export function LocalModelCard({
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
        <AcoesModeloInstalado
          modelo={modelo}
          isActivating={isActivating}
          isDeleting={isDeleting}
          onAtivar={onAtivar}
          onDesinstalar={onDesinstalar}
        />
      </div>
    </CardComCaracteristicas>
  );
}

function classeCardPreset(isSelected: boolean, instalado: boolean): string {
  if (isSelected) return "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs";
  if (instalado) return "border-slate-300 bg-slate-50/50";
  return "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs";
}

function rotuloAtivar(isActivating: boolean, isSelected: boolean): string {
  if (isActivating) return "Ativando...";
  return isSelected ? "Modelo Ativo" : "Ativar Modelo";
}

function AcaoPreset({
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
  if (!instalado) {
    return (
      <button
        type="button"
        disabled={isDownloading}
        onClick={() => onBaixar(preset.tag)}
        className="w-full rounded-lg bg-slate-900 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50 transition-colors cursor-pointer shadow-2xs"
      >
        {isDownloading ? "Baixando..." : "Baixar Modelo"}
      </button>
    );
  }
  const isSelected = instalado.is_active;
  return (
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
      {rotuloAtivar(isActivating, isSelected)}
    </button>
  );
}

export function LocalPresetCard({
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
        className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${classeCardPreset(isSelected, !!instalado)}`}
      >
        <div>
          <div className="flex items-center justify-between gap-2">
            <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
              {preset.provider}
            </span>
            <SeloAtivoInstalado instalado={!!instalado} isSelected={isSelected} />
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
          <AcaoPreset
            preset={preset}
            instalado={instalado}
            isDownloading={isDownloading}
            isActivating={isActivating}
            onAtivar={onAtivar}
            onBaixar={onBaixar}
          />
        </div>
      </div>
    </CardComCaracteristicas>
  );
}
