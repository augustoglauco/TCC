import { ProductCard } from "@/components/products/ProductCard";
import type { Produto } from "@/lib/api/products";

interface CatalogoConteudoProps {
  loading: boolean;
  error: string | null;
  products: Produto[];
  groupedProducts: Record<string, Produto[]>;
  onRetry: () => void;
  onOpenZoom: (url: string, nome: string) => void;
}

/** Estado de carregamento / erro / vazio / grupos de produtos por categoria. */
export function CatalogoConteudo({
  loading,
  error,
  products,
  groupedProducts,
  onRetry,
  onOpenZoom,
}: CatalogoConteudoProps) {
  return (
    <>
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#16c0dd] border-t-transparent" />
          <p className="mt-3 text-sm font-medium">Carregando catálogo do banco de dados...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700">
          <p className="font-semibold">{error}</p>
          <button
            type="button"
            onClick={() => onRetry()}
            className="mt-3 inline-flex items-center rounded-lg bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-700 transition-colors cursor-pointer"
          >
            Tentar novamente
          </button>
        </div>
      ) : products.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-12 text-center text-slate-600">
          <span className="text-3xl">🔍</span>
          <h3 className="mt-2 text-base font-bold text-slate-900">Nenhum produto encontrado</h3>
          <p className="mt-1 text-xs text-slate-500">
            Tente buscar por outros termos ou selecionar outra categoria.
          </p>
        </div>
      ) : (
        /* Renderização dos Grupos por Categoria com Scroll Interno */
        <div className="max-h-[62vh] sm:max-h-[70vh] overflow-y-auto pr-1.5 sm:pr-3 space-y-8 rounded-[20px] border border-[#e3e3e8] bg-white p-4 sm:p-6 shadow-sm">
          {Object.entries(groupedProducts).map(([categoria, prodsDaCategoria]) => (
            <section key={categoria} className="space-y-4">
              {/* Título da Categoria */}
              <div className="flex items-center gap-3 border-b border-[#e3e3e8] pb-2.5">
                <h2 className="text-lg font-extrabold text-[#191919] flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-[#16c0dd]" />
                  {categoria}
                </h2>
                <span className="rounded-full bg-[#f6f6f6] border border-[#e3e3e8] px-2.5 py-0.5 text-xs font-bold text-[#4d4d52]">
                  {prodsDaCategoria.length} {prodsDaCategoria.length === 1 ? "item" : "itens"}
                </span>
              </div>

              {/* Grid de Cards da Categoria (1 col mobile, 2 cols tablet 7'', 3-4 cols desktop) */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {prodsDaCategoria.map((prod) => (
                  <ProductCard
                    key={prod.id}
                    product={prod}
                    onOpenZoom={(url) => onOpenZoom(url, prod.nome)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
