"use client";
/* eslint-disable @next/next/no-img-element */

import { useEffect, useMemo, useState } from "react";
import { fetchProductCategories, fetchProducts, Produto } from "@/lib/api/products";
import { ProductCard } from "@/components/products/ProductCard";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";

const ITEMS_PER_PAGE = 12;

const FEATURED_BANNER_THUMBS = [
  { src: "/images/produtos/idface-max.jpg", label: "iDFace Max" },
  { src: "/images/produtos/idblock-next-facial.jpg", label: "iDBlock Next Facial" },
  { src: "/images/produtos/rep-idclass.jpg", label: "REP iDClass" },
  { src: "/images/produtos/idaccess-pro.jpg", label: "iDAccess Pro" },
];

export default function ProdutosPage() {
  const [products, setProducts] = useState<Produto[]>([]);
  const [categories, setCategories] = useState<string[]>(["Todas"]);
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
    // Liga o indicador de carregamento antes do fetch — falso positivo conhecido
    // de `react-hooks/set-state-in-effect`, mesmo caso de `app/admin/ingestao/page.tsx`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
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
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 sm:py-10 space-y-8">
      {/* Modal de Zoom de Imagem */}
      {zoomImageUrl && (
        <ImageZoomModal
          imageUrl={zoomImageUrl}
          productName={zoomProductName}
          onClose={handleCloseZoom}
        />
      )}

      {/* Cabeçalho estilo Galeria Técnica M3 Glass com Fotos Reais */}
      <div className="relative overflow-hidden rounded-[24px] bg-[#100d0b] border border-white/10 p-6 sm:p-10 lg:p-12 text-white shadow-2xl space-y-6">
        {/* Background Product Image with Frosted Shade */}
        <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
          <img
            src="/images/produtos/idblock-facial-inox.jpg"
            alt=""
            className="h-full w-full object-cover object-center opacity-20 scale-105"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-[#100d0b] via-[#100d0b]/92 to-[#100d0b]/75" />
        </div>

        {/* Giant Watermark */}
        <span
          aria-hidden="true"
          className="m3-watermark-dark right-6 -top-2 text-[70px] sm:text-[130px] lg:text-[175px]"
        >
          Catalogo
        </span>

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-end justify-between gap-6">
          <div className="space-y-2.5 max-w-2xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-[#16c0dd]/40 bg-[#16c0dd]/10 px-3.5 py-1 text-[11px] font-extrabold uppercase tracking-[0.2em] text-[#16c0dd]">
              <span className="h-2 w-2 rounded-full bg-[#16c0dd] shadow-[0_0_8px_#16c0dd]" />
              Catálogo Técnico Oficial
            </span>
            <h1 className="text-2xl sm:text-4xl lg:text-[42px] font-extrabold tracking-tight text-white leading-tight">
              Equipamentos &amp; <span className="text-[#16c0dd]">Hardware Industrial</span>
            </h1>
            <p className="text-xs sm:text-sm text-white/75 leading-relaxed">
              Consulte produtos cadastrados no banco de dados, verifique disponibilidade de estoque
              por Centro de Distribuição e solicite cotações em tempo real via MCP B2B.
            </p>
          </div>

          {/* Campo de Busca por Texto + Miniaturas Fotográficas */}
          <div className="flex flex-col sm:flex-row lg:flex-col items-stretch sm:items-center lg:items-end gap-4 shrink-0">
            <div className="hidden sm:flex items-center gap-2">
              {FEATURED_BANNER_THUMBS.map((thumb) => (
                <button
                  key={thumb.src}
                  type="button"
                  onClick={() => handleOpenZoom(thumb.src, thumb.label)}
                  title={`Ampliar ${thumb.label}`}
                  className="m3-photo-card h-12 w-12 rounded-xl border-2 border-white/80 bg-white overflow-hidden shadow-md hover:border-[#16c0dd] hover:scale-105 transition-all cursor-pointer"
                >
                  <img src={thumb.src} alt={thumb.label} className="h-full w-full object-cover" />
                </button>
              ))}
            </div>

            <div className="relative w-full lg:w-80 shrink-0">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por nome ou código..."
                className="w-full rounded-full border border-white/20 bg-white/10 backdrop-blur-md pl-10 pr-4 py-3 text-xs sm:text-sm text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-[#16c0dd] shadow-inner"
              />
              <svg
                className="absolute left-3.5 top-3.5 h-4 w-4 text-[#16c0dd]"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
          </div>
        </div>

        {/* Filtros de Categoria em Pílulas com Rolagem Horizontal Touch */}
        <div className="relative z-10 pt-4 border-t border-white/15 flex items-center gap-2 overflow-x-auto scrollbar-none pb-1">
          {categories.map((cat) => {
            const isActive = selectedCategory === cat;
            return (
              <button
                key={cat}
                type="button"
                onClick={() => {
                  setSelectedCategory(cat);
                  setCurrentPage(1);
                }}
                className={`shrink-0 rounded-full px-4 py-2 text-xs font-extrabold transition-all cursor-pointer ${
                  isActive
                    ? "bg-[#16c0dd] text-[#191919] shadow-md shadow-[#16c0dd]/30"
                    : "border border-white/15 bg-white/5 text-white/80 hover:border-[#16c0dd]/50 hover:bg-white/10 hover:text-white"
                }`}
              >
                {cat === "Todas" ? "Todas as categorias" : cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* Indicador de Estado de Carregamento / Erro / Conteúdo */}
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
        <div className="mt-10 border-t border-[#e3e3e8] pt-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="text-xs text-[#4d4d52]">
            Exibindo{" "}
            <span className="font-bold text-[#191919]">
              {Math.min((currentPage - 1) * ITEMS_PER_PAGE + 1, totalItems)}
            </span>{" "}
            a{" "}
            <span className="font-bold text-[#191919]">
              {Math.min(currentPage * ITEMS_PER_PAGE, totalItems)}
            </span>{" "}
            de <span className="font-bold text-[#191919]">{totalItems}</span> produtos
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
                    ? "bg-[#16c0dd] text-[#191919] shadow-xs"
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
