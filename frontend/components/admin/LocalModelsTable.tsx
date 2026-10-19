"use client";

import {
  LocalModelCard,
  LocalPresetCard,
  POPULAR_LOCAL_PRESETS,
} from "@/components/admin/LocalModelCards";
import { BannerModeloAtivo, ConfirmarDesinstalacao } from "@/components/admin/LocalModelsPartes";
import { useLocalModelsAcoes } from "@/lib/hooks/useLocalModelsAcoes";
import type { LocalModel } from "@/lib/types/localModels";

export interface LocalModelsTableProps {
  models: LocalModel[];
  onChanged: () => void;
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

function ModelosInstaladosVazio() {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50/50 p-8 text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-2xl">
        📦
      </div>
      <h4 className="mt-3 text-sm font-bold text-slate-800">Nenhum modelo local baixado ainda</h4>
      <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
        Escolha um dos modelos recomendados abaixo ou informe a tag de um modelo para realizar o
        download no servidor.
      </p>
    </div>
  );
}

export function LocalModelsTable({ models, onChanged, onError, onSuccess }: LocalModelsTableProps) {
  const acoes = useLocalModelsAcoes({ onChanged, onError, onSuccess });
  const activeModel = models.find((m) => m.is_active);

  return (
    <div className="space-y-8">
      {acoes.confirmarDelete && (
        <ConfirmarDesinstalacao
          modelo={acoes.confirmarDelete}
          onCancelar={() => acoes.setConfirmarDelete(null)}
          onConfirmar={acoes.handleDesinstalar}
        />
      )}
      <BannerModeloAtivo activeModel={activeModel} />

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
          <ModelosInstaladosVazio />
        ) : (
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {models.map((modelo) => (
              <LocalModelCard
                key={modelo.name}
                modelo={modelo}
                isActivating={acoes.processandoTag === modelo.name}
                isDeleting={acoes.deletandoTag === modelo.name}
                onAtivar={acoes.handleAtivar}
                onDesinstalar={(m) => acoes.setConfirmarDelete(m)}
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
              isDownloading={acoes.baixandoPreset === preset.tag}
              isActivating={acoes.processandoTag === preset.tag}
              onAtivar={acoes.handleAtivar}
              onBaixar={acoes.handleBaixarPreset}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
