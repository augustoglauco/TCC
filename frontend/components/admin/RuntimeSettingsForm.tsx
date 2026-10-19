"use client";

import { useRuntimeSettingsForm } from "@/lib/hooks/useRuntimeSettingsForm";
import type { CamposRuntime } from "@/lib/hooks/useRuntimeSettingsForm";
import { RuntimeLlmParamsSection } from "./RuntimeLlmParamsSection";
import { RuntimeVramSection } from "./RuntimeVramSection";
import { RuntimeRouterSection } from "./RuntimeRouterSection";
import { RuntimeToneMonitorSection } from "./RuntimeToneMonitorSection";
import { RuntimeEstoqueSection } from "./RuntimeEstoqueSection";
import { RuntimeVisionSection } from "./RuntimeVisionSection";
import { RuntimeRagSection } from "./RuntimeRagSection";

export interface RuntimeSettingsFormProps {
  onError: (message: string) => void;
  onSuccess: (message: string) => void;
}

const NOME_ROTEADOR: Record<CamposRuntime["routerProvider"], string> = {
  jev_openrouter: "Jev OpenRouter",
  heuristica: "Heurística (Palavras-chave)",
  heuristica_llm: "Heurística + LLM Local",
};

function CarregandoParametros() {
  return (
    <div className="flex items-center justify-center py-12 text-slate-500">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
      <span className="ml-2.5 text-xs font-medium">Carregando parâmetros...</span>
    </div>
  );
}

function BannerRuntime({ routerProvider }: { routerProvider: CamposRuntime["routerProvider"] }) {
  return (
    <div className="rounded-2xl border border-indigo-200/80 bg-gradient-to-r from-indigo-50/80 via-blue-50/80 to-slate-50/80 p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="flex items-center gap-3.5">
        <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-indigo-600 text-white text-2xl shadow-sm">
          ⚙️
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-700">
              Parâmetros de Inferência &amp; Orquestração
            </span>
            <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mt-0.5">
            Roteador:{" "}
            <span className="font-mono text-indigo-900">{NOME_ROTEADOR[routerProvider]}</span>
          </h2>
        </div>
      </div>
      <div className="inline-flex items-center gap-1.5 rounded-xl bg-white px-3.5 py-1.5 text-xs font-semibold text-indigo-700 border border-indigo-200 shadow-2xs">
        <span>⚡ Configuração em Tempo de Execução</span>
      </div>
    </div>
  );
}

function RodapeRuntime({ salvando }: { salvando: boolean }) {
  return (
    <>
      <div className="rounded-xl border border-blue-200/80 bg-blue-50/60 p-4 shadow-2xs flex items-center justify-between gap-3 text-xs text-blue-900">
        <div className="flex items-center gap-2.5">
          <span className="text-base">💾</span>
          <div>
            <span className="font-bold block">Configurações Persistentes no Banco de Dados</span>
            <span className="text-blue-700 text-[11px]">
              Todos os parâmetros definidos nesta página são salvos no PostgreSQL e restaurados
              automaticamente ao reiniciar o backend.
            </span>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-2">
        <button
          type="submit"
          disabled={salvando}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-7 py-3 text-xs sm:text-sm font-bold text-white shadow-sm transition-all hover:bg-slate-800 disabled:opacity-50 cursor-pointer"
        >
          {salvando ? "Aplicando..." : "Aplicar"}
        </button>
      </div>
    </>
  );
}

export function RuntimeSettingsForm({ onError, onSuccess }: RuntimeSettingsFormProps) {
  const {
    carregado,
    campos,
    setCampo,
    acaoVramEmAndamento,
    salvando,
    salvar,
    carregarVram,
    liberarVram,
  } = useRuntimeSettingsForm({ onError, onSuccess });

  if (!carregado) return <CarregandoParametros />;

  return (
    <form onSubmit={salvar} className="space-y-8">
      <BannerRuntime routerProvider={campos.routerProvider} />

      <RuntimeLlmParamsSection
        temperatura={campos.temperatura}
        numCtx={campos.numCtx}
        topP={campos.topP}
        topK={campos.topK}
        repeatPenalty={campos.repeatPenalty}
        seed={campos.seed}
        localTimeout={campos.localTimeout}
        externalTimeout={campos.externalTimeout}
        onTemperatura={setCampo("temperatura")}
        onNumCtx={setCampo("numCtx")}
        onTopP={setCampo("topP")}
        onTopK={setCampo("topK")}
        onRepeatPenalty={setCampo("repeatPenalty")}
        onSeed={setCampo("seed")}
        onLocalTimeout={setCampo("localTimeout")}
        onExternalTimeout={setCampo("externalTimeout")}
      />

      <RuntimeVramSection
        keepAlive={campos.keepAlive}
        warmupOnStartup={campos.warmupOnStartup}
        modelLoaded={campos.modelLoaded}
        vramBytes={campos.vramBytes}
        salvando={salvando}
        acaoVramEmAndamento={acaoVramEmAndamento}
        onKeepAlive={setCampo("keepAlive")}
        onWarmup={setCampo("warmupOnStartup")}
        onCarregar={carregarVram}
        onLiberar={liberarVram}
      />

      <RuntimeRouterSection
        routerProvider={campos.routerProvider}
        onChange={setCampo("routerProvider")}
      />

      <RuntimeToneMonitorSection
        enabled={campos.toneMonitorEnabled}
        provider={campos.toneMonitorProvider}
        onEnabled={setCampo("toneMonitorEnabled")}
        onProvider={setCampo("toneMonitorProvider")}
      />

      <RuntimeEstoqueSection
        mode={campos.estoqueAgentMode}
        llm={campos.estoqueAgentLlm}
        onMode={setCampo("estoqueAgentMode")}
        onLlm={setCampo("estoqueAgentLlm")}
      />

      <RuntimeVisionSection
        externalVisionModel={campos.externalVisionModel}
        imageInternalConfidence={campos.imageInternalConfidence}
        imageExternalConfidence={campos.imageExternalConfidence}
        onVisionModel={setCampo("externalVisionModel")}
        onInternalConfidence={setCampo("imageInternalConfidence")}
        onExternalConfidence={setCampo("imageExternalConfidence")}
      />

      <RuntimeRagSection
        ragTopK={campos.ragTopK}
        ragScoreThreshold={campos.ragScoreThreshold}
        ragSearchDomainFallback={campos.ragSearchDomainFallback}
        onTopK={setCampo("ragTopK")}
        onScoreThreshold={setCampo("ragScoreThreshold")}
        onDomainFallback={setCampo("ragSearchDomainFallback")}
      />

      <RodapeRuntime salvando={salvando} />
    </form>
  );
}
