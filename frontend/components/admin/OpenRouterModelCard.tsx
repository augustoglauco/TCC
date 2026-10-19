"use client";

import { useOpenRouterModelo } from "@/lib/hooks/useOpenRouterModelo";
import { ModelHistoryRow, ModelPresetCard } from "@/components/admin/OpenRouterCards";
import {
  FREE_MODELS,
  POPULAR_MODELS,
  type PresetModel,
} from "@/components/admin/OpenRouterPresets";

interface OpenRouterModelCardProps {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}

type Ativacao = {
  activeModel: string;
  activatingTag: string | null;
  onActivate: (tag: string) => void;
};

function GrupoPresets({
  modelos,
  isFree,
  ativacao,
}: {
  modelos: PresetModel[];
  isFree?: boolean;
  ativacao: Ativacao;
}) {
  return (
    <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
      {modelos.map((model) => (
        <ModelPresetCard
          key={model.tag}
          model={model}
          isSelected={ativacao.activeModel === model.tag}
          isActivating={ativacao.activatingTag === model.tag}
          isFree={isFree}
          onActivate={ativacao.onActivate}
        />
      ))}
    </div>
  );
}

function Carregando() {
  return (
    <div className="flex items-center justify-center py-12 text-slate-500">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      <span className="ml-2.5 text-xs font-medium">Carregando configurações do OpenRouter...</span>
    </div>
  );
}

function BannerModeloAtivo({ activeModel }: { activeModel: string }) {
  return (
    <div className="rounded-2xl border border-blue-200/80 bg-gradient-to-r from-blue-50/80 to-indigo-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3.5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white text-2xl shadow-sm">
          🌐
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700">
              Modelo Externo Ativo (OpenRouter)
            </span>
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 font-mono mt-0.5">{activeModel}</h2>
        </div>
      </div>

      <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-emerald-700 border border-emerald-200 shadow-2xs">
        <span>✓ Em Execução em Runtime</span>
      </div>
    </div>
  );
}

function SecaoModeloPersonalizado({
  customInput,
  setCustomInput,
  activatingTag,
  onActivate,
}: {
  customInput: string;
  setCustomInput: (v: string) => void;
  activatingTag: string | null;
  onActivate: (tag: string) => void;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:p-5 space-y-3 pt-2">
      <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
        <span>➕</span> Adicionar / Ativar Outro Modelo do OpenRouter
      </h3>
      <p className="text-xs text-slate-500">
        Insira a tag identificadora de qualquer modelo suportado pelo OpenRouter (ex.:{" "}
        <code className="rounded bg-slate-200 px-1 py-0.5 font-mono text-slate-800">
          deepseek/deepseek-chat
        </code>
        ).
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onActivate(customInput);
        }}
        className="flex flex-col sm:flex-row gap-2"
      >
        <input
          type="text"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="provedor/nome-do-modelo"
          className="flex-1 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs sm:text-sm font-mono text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
        />
        <button
          type="submit"
          disabled={!customInput.trim() || activatingTag !== null}
          className="rounded-lg bg-slate-900 px-5 py-2 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-40 transition-colors cursor-pointer"
        >
          Ativar Modelo
        </button>
      </form>
    </div>
  );
}

export function OpenRouterModelCard({ onError, onSuccess }: OpenRouterModelCardProps) {
  const m = useOpenRouterModelo({ onError, onSuccess });
  const ativacao: Ativacao = {
    activeModel: m.activeModel,
    activatingTag: m.activatingTag,
    onActivate: m.handleActivateModel,
  };

  if (m.loading) return <Carregando />;

  return (
    <div className="space-y-8">
      <BannerModeloAtivo activeModel={m.activeModel} />

      {/* Seção 1: Modelos Populares */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>⭐</span> Modelos Populares no OpenRouter
          </h3>
          <span className="text-xs text-slate-500">Modelos comerciais de alta performance</span>
        </div>

        <GrupoPresets modelos={POPULAR_MODELS} ativacao={ativacao} />
      </div>

      {/* Seção 2: Modelos Gratuitos (Free) */}
      <div className="space-y-3 pt-2 border-t border-slate-200/80">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <span>🎁</span> Modelos Gratuitos (Free Tier)
          </h3>
          <span className="text-xs text-emerald-700 font-semibold bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
            Sem Custo de Tokens (0$/1M)
          </span>
        </div>

        <GrupoPresets modelos={FREE_MODELS} isFree ativacao={ativacao} />
      </div>

      {/* Seção 3: Histórico de Modelos Selecionados */}
      {m.historyModels.length > 0 && (
        <div className="space-y-3 pt-2 border-t border-slate-200/80">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>🕒</span> Histórico de Selecionados / Salvos
            </h3>
            <span className="text-xs text-slate-500">
              Modelos ativados recentemente e salvos localmente
            </span>
          </div>

          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {m.historyModels.map((tag) => (
              <ModelHistoryRow
                key={tag}
                tag={tag}
                isSelected={m.activeModel === tag}
                isActivating={m.activatingTag === tag}
                onActivate={m.handleActivateModel}
                onRemove={m.handleRemoveFromHistory}
              />
            ))}
          </div>
        </div>
      )}

      <SecaoModeloPersonalizado
        customInput={m.customInput}
        setCustomInput={m.setCustomInput}
        activatingTag={m.activatingTag}
        onActivate={m.handleActivateModel}
      />
    </div>
  );
}
