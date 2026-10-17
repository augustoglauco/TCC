"use client";

import type { AdminProductStock } from "@/lib/types/adminProducts";

interface ProductFormEstoqueTabProps {
  estoques: AdminProductStock[];
  cdNome: string;
  cdQtd: string;
  updatingStock: boolean;
  onCdNome: (v: string) => void;
  onCdQtd: (v: string) => void;
  onSalvar: () => void;
}

export function ProductFormEstoqueTab({
  estoques,
  cdNome,
  cdQtd,
  updatingStock,
  onCdNome,
  onCdQtd,
  onSalvar,
}: ProductFormEstoqueTabProps) {
  return (
    <div className="space-y-4 py-2">
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
          📦 Atualizar Estoque por Centro de Distribuição
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Centro de Distribuição
            </label>
            <select
              value={cdNome}
              onChange={(e) => onCdNome(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 focus:border-blue-500 focus:outline-none"
            >
              <option value="CD-Matriz">CD-Matriz</option>
              <option value="CD-SP">CD-SP</option>
              <option value="CD-RJ">CD-RJ</option>
              <option value="CD-Sul">CD-Sul</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-700">
              Quantidade em Estoque
            </label>
            <input
              type="number"
              min="0"
              value={cdQtd}
              onChange={(e) => onCdQtd(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              disabled={updatingStock}
              onClick={onSalvar}
              className="w-full rounded-lg bg-blue-600 py-2 px-4 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs"
            >
              {updatingStock ? "Salvando..." : "Atualizar Estoque"}
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Estoques Cadastrados
        </h4>
        {estoques.length === 0 ? (
          <p className="text-xs text-slate-400 italic">Nenhum registro de estoque em CD ainda.</p>
        ) : (
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {estoques.map((est) => (
              <div key={est.id} className="flex items-center justify-between p-3 text-xs">
                <span className="font-semibold text-slate-900">{est.centro_distribuicao}</span>
                <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                  {est.quantidade} unidades
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
