"use client";

interface ProductCardActionsProps {
  emEstoque: boolean;
  onBuy: () => void;
  onQuote: () => void;
}

export function ProductCardActions({ emEstoque, onBuy, onQuote }: ProductCardActionsProps) {
  return (
    <div className="mt-5 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2">
      <button
        type="button"
        onClick={onBuy}
        disabled={!emEstoque}
        className={`flex items-center justify-center gap-1.5 rounded-xl py-2.5 px-3 text-xs font-bold transition-all cursor-pointer ${
          emEstoque
            ? "bg-blue-600 text-white hover:bg-blue-700 shadow-xs hover:shadow"
            : "bg-slate-200 text-slate-400 cursor-not-allowed"
        }`}
      >
        <span>🛒</span>
        <span>Comprar</span>
      </button>

      <button
        type="button"
        onClick={onQuote}
        className="flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 py-2.5 px-3 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors cursor-pointer"
      >
        <span>💬</span>
        <span>Cotar</span>
      </button>
    </div>
  );
}
