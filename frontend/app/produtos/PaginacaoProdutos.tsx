import { ITEMS_PER_PAGE } from "./useProdutosCatalogo";

interface PaginacaoProdutosProps {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  onChange: (page: number) => void;
}

/** Controle de paginação (server-side) do catálogo. */
export function PaginacaoProdutos({
  currentPage,
  totalPages,
  totalItems,
  onChange,
}: PaginacaoProdutosProps) {
  return (
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
          onClick={() => onChange(Math.max(currentPage - 1, 1))}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors cursor-pointer"
        >
          Anterior
        </button>

        {/* Números das Páginas */}
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
          <button
            key={page}
            type="button"
            onClick={() => onChange(page)}
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
          onClick={() => onChange(Math.min(currentPage + 1, totalPages))}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-slate-50 transition-colors cursor-pointer"
        >
          Próximo
        </button>
      </div>
    </div>
  );
}
