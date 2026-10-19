/* eslint-disable @next/next/no-img-element */

const FEATURED_BANNER_THUMBS = [
  { src: "/images/produtos/idface-max.jpg", label: "iDFace Max" },
  { src: "/images/produtos/idblock-next-facial.jpg", label: "iDBlock Next Facial" },
  { src: "/images/produtos/rep-idclass.jpg", label: "REP iDClass" },
  { src: "/images/produtos/idaccess-pro.jpg", label: "iDAccess Pro" },
];

interface CatalogoHeaderProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  categories: string[];
  selectedCategory: string;
  onSelectCategory: (cat: string) => void;
  onOpenZoom: (url: string, nome: string) => void;
}

/** Cabeçalho estilo Galeria Técnica M3 Glass com busca, miniaturas e pílulas de categoria. */
export function CatalogoHeader({
  searchQuery,
  onSearchChange,
  categories,
  selectedCategory,
  onSelectCategory,
  onOpenZoom,
}: CatalogoHeaderProps) {
  return (
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
                onClick={() => onOpenZoom(thumb.src, thumb.label)}
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
              onChange={(e) => onSearchChange(e.target.value)}
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
                onSelectCategory(cat);
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
  );
}
