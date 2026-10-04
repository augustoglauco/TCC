"use client";

import type { ModelCharacteristics } from "@/lib/types/modelCatalog";

const NOMES_MODALIDADE: Record<string, string> = {
  text: "Texto",
  image: "Imagem",
  audio: "Áudio",
  video: "Vídeo",
  file: "Arquivo",
  desconhecido: "Desconhecido",
};

const MODALIDADES_NAO_TEXTO = new Set(["image", "audio", "video"]);

function Chip({ modalidade }: { modalidade: string }) {
  const destaque = MODALIDADES_NAO_TEXTO.has(modalidade);
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
        destaque ? "bg-blue-100 text-blue-800" : "bg-slate-100 text-slate-600"
      }`}
    >
      {NOMES_MODALIDADE[modalidade] ?? modalidade}
    </span>
  );
}

function formatarContexto(contextLength: number | null): string | null {
  if (contextLength === null) return null;
  if (contextLength >= 1000) return `${Math.round(contextLength / 1000)}K tokens`;
  return `${contextLength} tokens`;
}

function formatarDataRelativa(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffHoras = Math.floor(diffMs / (1000 * 60 * 60));
  if (diffHoras < 1) return "agora há pouco";
  if (diffHoras < 24) return `há ${diffHoras}h`;
  return `há ${Math.floor(diffHoras / 24)}d`;
}

export interface ModelCharacteristicsPanelProps {
  data: ModelCharacteristics | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function ModelCharacteristicsPanel({
  data,
  loading,
  error,
  onRefresh,
}: ModelCharacteristicsPanelProps) {
  if (loading && !data) {
    return <div className="text-[11px] text-slate-500 italic">Carregando características...</div>;
  }

  if (!data) {
    return (
      <div className="text-[11px] text-slate-500 italic">
        {error ?? "Características indisponíveis no momento."}
      </div>
    );
  }

  const contexto = formatarContexto(data.context_length);

  return (
    <div className="space-y-1.5 text-left">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
          Entrada
        </span>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRefresh();
          }}
          disabled={loading}
          aria-label="Atualizar características"
          className="text-slate-400 hover:text-blue-600 disabled:opacity-40 cursor-pointer"
        >
          {loading ? "⏳" : "⟳"}
        </button>
      </div>
      <div className="flex flex-wrap gap-1">
        {data.input_modalities.map((m) => (
          <Chip key={m} modalidade={m} />
        ))}
      </div>

      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
        Saída
      </span>
      <div className="flex flex-wrap gap-1">
        {data.output_modalities.map((m) => (
          <Chip key={m} modalidade={m} />
        ))}
      </div>

      {contexto && <p className="text-[11px] text-slate-600">Contexto: {contexto}</p>}
      {data.parameter_size && (
        <p className="text-[11px] text-slate-600">Parâmetros: {data.parameter_size}</p>
      )}
      {data.quantization && (
        <p className="text-[11px] text-slate-600">Quantização: {data.quantization}</p>
      )}
      {data.pricing_prompt_per_1k !== null && (
        <p className="text-[11px] text-slate-600">
          Preço: ${data.pricing_prompt_per_1k.toFixed(5)}/1K entrada · $
          {data.pricing_completion_per_1k?.toFixed(5)}/1K saída
        </p>
      )}
      {data.knowledge_cutoff && (
        <p className="text-[11px] text-slate-600">Dados até: {data.knowledge_cutoff}</p>
      )}
      <p className="text-[10px] text-slate-400">
        Atualizado {formatarDataRelativa(data.fetched_at)}
      </p>
    </div>
  );
}
