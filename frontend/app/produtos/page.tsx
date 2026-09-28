"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchProductCategories, fetchProducts, Produto } from "@/lib/api/products";
import { ProductCard } from "@/components/products/ProductCard";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";

const ITEMS_PER_PAGE = 12;

export default function ProdutosPage() {
  const [products, setProducts] = useState<Produto[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [totalItems, setTotalItems] = useState(0);

  const [selectedCategory, setSelectedCategory] = useState("Todas");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Estado para modal de zoom de imagem
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);
  const [zoomProductName, setZoomProductName] = useState("");

  // Debounce do campo de busca (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setCurrentPage(1); // Reseta para primeira página ao buscar
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Carrega categorias distintas na montagem
  useEffect(() => {
    fetchProductCategories()
      .then((cats) => setCategories(["Todas", ...cats]))
      .catch((err) => console.error("Falha ao carregar categorias:", err));
  }, []);

  // Carrega lista de produtos do backend (com filtro, busca e paginação de servidor)
  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    const offset = (currentPage - 1) * ITEMS_PER_PAGE;

    fetchProducts({
      termo: debouncedSearch,
      categoria: selectedCategory,
      limit: ITEMS_PER_PAGE,
      offset,
    })
      .then((data) => {
        if (isMounted) {
          setProducts(data.items);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error("Erro ao carregar catálogo:", err);
          setError("Não foi possível carregar o catálogo de produtos do servidor.");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [debouncedSearch, selectedCategory, currentPage]);

  // Agrupa os produtos da página atual por Categoria
  const groupedProducts = useMemo(() => {
    const groups: Record<string, Produto[]> = {};
    products.forEach((prod) => {
      const cat = prod.categoria || "Outros";
      if (!groups[cat]) {
        groups[cat] = [];
      }
      groups[cat].push(prod);
    });
    return groups;
  }, [products]);

  // Total de páginas
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE) || 1;

  const handleOpenZoom = (url: string, nome: string) => {
    setZoomImageUrl(url);
    setZoomProductName(nome);
  };

  const handleCloseZoom = () => {
    setZoomImageUrl(null);
    setZoomProductName("");
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:py-12 space-y-8">
      {/* Modal de Zoom de Imagem */}
      {zoomImageUrl && (
        <ImageZoomModal
          imageUrl={zoomImageUrl}
          productName={zoomProductName}
          onClose={handleCloseZoom}
        />
      )}

      {/* Cabeçalho da página */}
      <div className="border-b border-slate-200 pb-6 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700 border border-blue-100">
            <span>📦</span> Catálogo de Produtos & Peças
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Produtos Industriais
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Consulte produtos cadastrados no Banco de Dados, verifique disponibilidade de estoque e solicite cotações em tempo real.
          </p>
        </div>

        {/* Barra de Filtros e Busca */}
        <div className="flex flex-col sm:flex-row items-center gap-3 w-full md:w-auto">
          {/* Seletor de Categorias */}
          <div className="w-full sm:w-48">
            <select
              value={selectedCategory}
              onChange={(e) => {
                setSelectedCategory(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-xs cursor-pointer"
            >
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat === "Todas" ? "Todas as categorias" : cat}
                </option>
              ))}
            </select>
          </div>

          {/* Campo de Busca por Texto */}
          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar por nome ou código..."
              className="w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 py-2 text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-xs"
            />
            <svg
              className="absolute left-3 top-2.5 h-4 w-4 text-slate-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Indicador de Estado de Carregamento / Erro / Conteúdo */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          <p className="mt-3 text-sm font-medium">Carregando catálogo do banco de dados...</p>
        </div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-red-700">
          <p className="font-semibold">{error}</p>
          <button
            type="button"
            onClick={() => setCurrentPage(1)}
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
        /* Renderização dos Grupos por Categoria */
        <div className="space-y-10">
          {Object.entries(groupedProducts).map(([categoria, prodsDaCategoria]) => (
            <section key={categoria} className="space-y-4">
              {/* Título da Categoria */}
              <div className="flex items-center gap-3 border-b border-slate-200 pb-2">
                <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-blue-600" />
                  {categoria}
                </h2>
                <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                  {prodsDaCategoria.length} {prodsDaCategoria.length === 1 ? "item" : "itens"}
                </span>
              </div>

              {/* Grid de Cards da Categoria */}
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {prodsDaCategoria.map((prod) => (
                  <ProductCard
                    key={prod.id}
                    product={prod}
                    onOpenZoom={(url) => handleOpenZoom(url, prod.nome)}
                  />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      {/* Controle de Paginação (Server-Side) */}
      {!loading && !error && totalItems > 0 && (
        <div className="mt-10 border-t border-slate-200 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs text-slate-600">
            Exibindo <span className="font-bold text-slate-900">{Math.min((currentPage - 1) * ITEMS_PER_PAGE + 1, totalItems)}</span> a{" "}
            <span className="font-bold text-slate-900">{Math.min(currentPage * ITEMS_PER_PAGE, totalItems)}</span> de{" "}
            <span className="font-bold text-slate-900">{totalItems}</span> produtos
          </div>

          <div className="flex items-center gap-1.5">
            {/* Botão Anterior */}
            <button
              type="button"
              disabled={currentPage === 1}
              onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Anterior
            </button>

            {/* Números das Páginas */}
            {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
              <button
                key={page}
                type="button"
                onClick={() => setCurrentPage(page)}
                className={`h-8 w-8 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  currentPage === page
                    ? "bg-blue-600 text-white shadow-xs"
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {page}
              </button>
            ))}

            {/* Botão Próximo */}
            <button
              type="button"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors cursor-pointer"
            >
              Próximo
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
