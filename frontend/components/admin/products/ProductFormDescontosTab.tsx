"use client";

import type { AdminProductVolumeDiscount } from "@/lib/types/adminProducts";

interface ProductFormDescontosTabProps {
  descontos: AdminProductVolumeDiscount[];
  descQtdMin: string;
  descPercentual: string;
  updatingDiscount: boolean;
  onQtdMin: (v: string) => void;
  onPercentual: (v: string) => void;
  onAdicionar: () => void;
  onRemover: (id: string) => void;
}

export function ProductFormDescontosTab({
  descontos,
  descQtdMin,
  descPercentual,
  updatingDiscount,
  onQtdMin,
  onPercentual,
  onAdicionar,
  onRemover,
}: ProductFormDescontosTabProps) {
  return (
    <div className="space-y-4 py-2">
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
          🏷️ Adicionar Faixa de Desconto por Volume
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Qtd Mínima (Unidades)
            </label>
            <input
              type="number"
              min="1"
              value={descQtdMin}
              onChange={(e) => onQtdMin(e.target.value)}
              placeholder="ex: 5"
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700">Desconto (%)</label>
            <input
              type="number"
              step="0.5"
              min="0.5"
              max="100"
              value={descPercentual}
              onChange={(e) => onPercentual(e.target.value)}
              placeholder="ex: 10"
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              disabled={updatingDiscount}
              onClick={onAdicionar}
              className="w-full rounded-lg bg-blue-600 py-2 px-4 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs"
            >
              {updatingDiscount ? "Adicionando..." : "+ Adicionar Faixa"}
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Faixas de Desconto Ativas
        </h4>
        {descontos.length === 0 ? (
          <p className="text-xs text-slate-400 italic">Nenhum desconto por volume configurado.</p>
        ) : (
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {descontos.map((desc) => (
              <div key={desc.id} className="flex items-center justify-between p-3 text-xs">
                <div>
                  <span className="font-semibold text-slate-900">
                    A partir de {desc.quantidade_minima} unidades:
                  </span>
                  <span className="ml-2 font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                    {desc.percentual_desconto}% OFF
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => onRemover(desc.id)}
                  className="text-red-500 hover:text-red-700 font-bold p-1 cursor-pointer"
                  title="Remover faixa de desconto"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
