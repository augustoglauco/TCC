"use client";

import SearchableSelect from "@/components/ui/SearchableSelect";
import type { AdminProduct, AdminProductCompatibility } from "@/lib/types/adminProducts";

interface ProductFormCompatibilidadesTabProps {
  produtoId: number;
  compatividades: AdminProductCompatibility[];
  compativelSelectedId: string;
  updatingCompatibility: boolean;
  allProducts: AdminProduct[];
  onSelectCompativel: (v: string) => void;
  onAdicionar: () => void;
  onRemover: (id: number) => void;
}

export function ProductFormCompatibilidadesTab({
  produtoId,
  compatividades,
  compativelSelectedId,
  updatingCompatibility,
  allProducts,
  onSelectCompativel,
  onAdicionar,
  onRemover,
}: ProductFormCompatibilidadesTabProps) {
  return (
    <div className="space-y-4 py-2">
      <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
          🔗 Vincular Produto Compatível
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Selecione o produto compatível do catálogo
            </label>
            <SearchableSelect
              options={allProducts
                .filter((p) => p.id !== produtoId)
                .map((p) => ({
                  value: String(p.id),
                  label: `#${p.id} - ${p.nome}`,
                  sublabel: p.categoria || "Sem categoria",
                }))}
              value={compativelSelectedId}
              onChange={onSelectCompativel}
              placeholder="-- Pesquise e selecione um produto --"
              disabled={updatingCompatibility}
            />
          </div>
          <div className="flex items-end">
            <button
              type="button"
              disabled={!compativelSelectedId || updatingCompatibility}
              onClick={onAdicionar}
              className="w-full sm:w-auto rounded-lg bg-blue-600 py-2 px-5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs shrink-0"
            >
              {updatingCompatibility ? "Viculando..." : "+ Vincular Compatível"}
            </button>
          </div>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
          Produtos Compatíveis Conectados
        </h4>
        {compatividades.length === 0 ? (
          <p className="text-xs text-slate-400 italic">
            Nenhum vínculo de compatibilidade cadastrado ainda.
          </p>
        ) : (
          <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
            {compatividades.map((comp) => (
              <div key={comp.id} className="flex items-center justify-between p-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-slate-400">#{comp.compativel_com_id}</span>
                  <span className="font-semibold text-slate-900">{comp.compativel_nome}</span>
                  {comp.categoria && (
                    <span className="text-[10px] font-semibold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                      {comp.categoria}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => onRemover(comp.compativel_com_id)}
                  className="text-red-500 hover:text-red-700 font-bold p-1 cursor-pointer"
                  title="Desvincular compatibilidade"
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
