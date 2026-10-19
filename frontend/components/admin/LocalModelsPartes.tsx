"use client";

import { formatarTamanho } from "@/components/admin/LocalModelCards";
import type { LocalModel } from "@/lib/types/localModels";

export function ConfirmarDesinstalacao({
  modelo,
  onCancelar,
  onConfirmar,
}: {
  modelo: LocalModel;
  onCancelar: () => void;
  onConfirmar: (m: LocalModel) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xl max-w-sm w-full mx-4">
        <h3 className="text-base font-bold text-slate-900">🗑 Desinstalar modelo?</h3>
        <p className="mt-2 text-sm text-slate-600">
          Tem certeza que deseja remover{" "}
          <span className="font-mono font-bold text-slate-900">{modelo.name}</span> (
          {formatarTamanho(modelo.size_bytes)}) do Ollama? Esta ação não pode ser desfeita.
        </p>
        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={onCancelar}
            className="flex-1 rounded-lg border border-slate-200 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={() => onConfirmar(modelo)}
            className="flex-1 rounded-lg bg-red-600 py-2 text-xs font-bold text-white hover:bg-red-700 transition-colors cursor-pointer"
          >
            Sim, remover
          </button>
        </div>
      </div>
    </div>
  );
}

export function BannerModeloAtivo({ activeModel }: { activeModel: LocalModel | undefined }) {
  return (
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
  );
}
