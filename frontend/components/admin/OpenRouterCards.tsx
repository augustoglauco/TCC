"use client";

import { Tooltip } from "@/components/ui/Tooltip";
import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import { useModelCharacteristics } from "@/lib/hooks/useModelCharacteristics";
import type { PresetModel } from "@/components/admin/OpenRouterPresets";

// Envolve cada card com o tooltip de características do modelo (hover),
// centralizando a chamada do hook para não repeti-la em cada `.map`.
function CardComCaracteristicas({ tag, children }: { tag: string; children: React.ReactElement }) {
  const { data, loading, error, refresh } = useModelCharacteristics("openrouter", tag);
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

const ACENTO = {
  free: {
    selecionado: "border-emerald-500 bg-emerald-50/40 ring-1 ring-emerald-500 shadow-xs",
    botao: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-2xs",
    selo: "bg-emerald-100 text-emerald-800",
    badgeAtivo: "bg-emerald-600 text-white",
    rotuloBotao: "Ativar Grátis",
  },
  pago: {
    selecionado: "border-blue-500 bg-blue-50/40 ring-1 ring-blue-500 shadow-xs",
    botao: "bg-blue-600 text-white hover:bg-blue-700 shadow-2xs",
    selo: "bg-slate-100 text-slate-600",
    badgeAtivo: "bg-emerald-100 text-emerald-800",
    rotuloBotao: "Ativar Modelo",
  },
};

function rotuloAtivacao(isSelected: boolean, isActivating: boolean, padrao: string) {
  if (isActivating) return "Ativando...";
  return isSelected ? "Modelo Ativo" : padrao;
}

export function ModelPresetCard({
  model,
  isSelected,
  isActivating,
  isFree,
  onActivate,
}: {
  model: PresetModel;
  isSelected: boolean;
  isActivating: boolean;
  isFree?: boolean;
  onActivate: (tag: string) => void;
}) {
  const acento = isFree ? ACENTO.free : ACENTO.pago;
  return (
    <CardComCaracteristicas tag={model.tag}>
      <div
        className={`flex flex-col justify-between rounded-xl border p-4 transition-all ${
          isSelected
            ? acento.selecionado
            : "border-slate-200 bg-white hover:border-slate-300 hover:shadow-2xs"
        }`}
      >
        <div>
          <div className="flex items-center justify-between gap-2">
            <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${acento.selo}`}>
              {isFree ? "GRATUITO" : model.provider}
            </span>
            {isSelected && (
              <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${acento.badgeAtivo}`}>
                Ativo
              </span>
            )}
          </div>
          <h4 className="mt-2 font-bold text-slate-900 text-sm">{model.name}</h4>
          <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{model.description}</p>
          <code className="mt-2 block text-[10px] font-mono text-slate-400 truncate">
            {model.tag}
          </code>
        </div>
        <div className="mt-4 pt-3 border-t border-slate-100">
          <button
            type="button"
            disabled={isSelected || isActivating}
            onClick={() => onActivate(model.tag)}
            className={`w-full rounded-lg py-2 text-xs font-bold transition-colors cursor-pointer ${
              isSelected ? "bg-slate-100 text-slate-400 cursor-default" : acento.botao
            }`}
          >
            {rotuloAtivacao(isSelected, isActivating, acento.rotuloBotao)}
          </button>
        </div>
      </div>
    </CardComCaracteristicas>
  );
}

export function ModelHistoryRow({
  tag,
  isSelected,
  isActivating,
  onActivate,
  onRemove,
}: {
  tag: string;
  isSelected: boolean;
  isActivating: boolean;
  onActivate: (tag: string) => void;
  onRemove: (tag: string, e: React.MouseEvent) => void;
}) {
  return (
    <CardComCaracteristicas tag={tag}>
      <div className="flex items-center justify-between gap-3 p-3 sm:px-4 hover:bg-slate-50 transition-colors">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={`h-2 w-2 rounded-full shrink-0 ${isSelected ? "bg-emerald-500" : "bg-slate-300"}`}
          />
          <span className="font-mono text-xs font-semibold text-slate-900 truncate" title={tag}>
            {tag}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {isSelected ? (
            <span className="rounded bg-emerald-100 px-2.5 py-1 text-[11px] font-bold text-emerald-800">
              Ativo
            </span>
          ) : (
            <button
              type="button"
              disabled={isActivating}
              onClick={() => onActivate(tag)}
              className="rounded-lg bg-slate-900 px-3 py-1 text-xs font-semibold text-white hover:bg-slate-800 transition-colors cursor-pointer"
            >
              {isActivating ? "Ativando..." : "Ativar"}
            </button>
          )}
          {!isSelected && (
            <button
              type="button"
              onClick={(e) => onRemove(tag, e)}
              className="rounded p-1 text-slate-400 hover:text-red-600 hover:bg-red-50 transition-colors cursor-pointer"
              title="Remover do histórico"
              aria-label="Remover do histórico"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
    </CardComCaracteristicas>
  );
}
