"use client";

import { ModelCharacteristicsPanel } from "@/components/admin/ModelCharacteristicsPanel";
import { CampoNomeModelo, ErroPull, ProgressoPull } from "@/components/admin/PullModelParts";
import { ehTagHuggingFace, useHfPreview } from "@/lib/hooks/useHfPreview";
import { usePullModel } from "@/lib/hooks/usePullModel";

export interface PullModelFormProps {
  onPulled: () => void;
}

export function PullModelForm({ onPulled }: PullModelFormProps) {
  const { nome, setNome, enviando, progresso, error, submit } = usePullModel(onPulled);
  const { previewHf, previewHfLoading, previewHfError, refreshPreview } = useHfPreview(nome);

  return (
    <form onSubmit={submit} className="space-y-4">
      <CampoNomeModelo nome={nome} enviando={enviando} onChange={setNome} />

      {ehTagHuggingFace(nome) && (
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3">
          <ModelCharacteristicsPanel
            data={previewHf}
            loading={previewHfLoading}
            error={previewHfError}
            onRefresh={refreshPreview}
          />
        </div>
      )}

      {progresso && <ProgressoPull progresso={progresso} />}
      {error && <ErroPull mensagem={error} />}
    </form>
  );
}
