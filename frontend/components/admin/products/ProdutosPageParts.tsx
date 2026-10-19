import CategoryFilter from "@/components/admin/products/CategoryFilter";
import type { MetricasProdutos } from "@/lib/hooks/useAdminProdutos";

export function ProdutosHeader({ onImport, onNew }: { onImport: () => void; onNew: () => void }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Catálogo de Produtos</h1>
        <p className="text-xs sm:text-sm text-gray-500 mt-0.5">
          Cadastre produtos, custos e fotos vetorizadas no catálogo visual CLIP para atendimento
          inteligente no chat.
        </p>
      </div>

      <div className="flex items-center gap-2.5">
        <button
          type="button"
          onClick={onImport}
          className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
        >
          <span>📥</span>
          <span>Importar Catálogo (PDF/Fotos)</span>
        </button>
        <button
          type="button"
          onClick={onNew}
          className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
        >
          <span>+</span>
          <span>Novo Produto</span>
        </button>
      </div>
    </div>
  );
}

export function ProdutosMetricas({ metricas }: { metricas: MetricasProdutos }) {
  const { total, comFoto, margemMedia } = metricas;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
        <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Total de Produtos
        </div>
        <div className="mt-1 text-2xl font-bold text-gray-900">{total}</div>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
        <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Com Foto / Vetorizados no CLIP
        </div>
        <div className="mt-1 text-2xl font-bold text-emerald-600 flex items-center gap-1.5">
          <span>{comFoto}</span>
          <span className="text-xs font-medium text-gray-400">
            ({total > 0 ? Math.round((comFoto / total) * 100) : 0}%)
          </span>
        </div>
      </div>
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
        <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Margem de Lucro Média
        </div>
        <div className="mt-1 text-2xl font-bold text-blue-600">
          {margemMedia !== null ? `+${margemMedia}%` : "-"}
        </div>
      </div>
    </div>
  );
}

function FiltrosAtivos({
  selected,
  onRemove,
  onClear,
}: {
  selected: string[];
  onRemove: (cat: string) => void;
  onClear: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-200/70">
      <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
        Filtros ativos ({selected.length}):
      </span>
      {selected.map((cat) => (
        <span
          key={cat}
          className="inline-flex items-center gap-1.5 rounded-full bg-blue-100/80 border border-blue-200 px-3 py-0.5 text-xs font-semibold text-blue-800"
        >
          <span>{cat}</span>
          <button
            type="button"
            onClick={() => onRemove(cat)}
            className="rounded-full text-blue-600 hover:bg-blue-200 hover:text-blue-900 h-3.5 w-3.5 inline-flex items-center justify-center transition-colors"
            title={`Remover filtro ${cat}`}
          >
            ✕
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={onClear}
        className="text-xs font-medium text-red-600 hover:text-red-800 underline transition-colors ml-1"
      >
        Limpar todas
      </button>
    </div>
  );
}

export function ProdutosFiltros({
  termo,
  onTermoChange,
  selectedCategories,
  onCategoriesChange,
  availableCategories,
  categoryCounts,
  onRemoveCategory,
}: {
  termo: string;
  onTermoChange: (v: string) => void;
  selectedCategories: string[];
  onCategoriesChange: (cats: string[]) => void;
  availableCategories: string[];
  categoryCounts: Record<string, number>;
  onRemoveCategory: (cat: string) => void;
}) {
  return (
    <div className="bg-gray-50/90 p-4 rounded-xl border border-gray-200 space-y-3">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="relative flex-1">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">🔍</span>
          <input
            type="text"
            value={termo}
            onChange={(e) => onTermoChange(e.target.value)}
            placeholder="Buscar por nome, modelo, especificações ou descrição..."
            className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <CategoryFilter
          selectedCategories={selectedCategories}
          onChange={onCategoriesChange}
          availableCategories={availableCategories}
          categoryCounts={categoryCounts}
        />
      </div>

      {selectedCategories.length > 0 && (
        <FiltrosAtivos
          selected={selectedCategories}
          onRemove={onRemoveCategory}
          onClear={() => onCategoriesChange([])}
        />
      )}
    </div>
  );
}
