"use client";

interface ProductCardHeaderProps {
  categoria: string;
  emEstoque: boolean;
  totalEstoque: number;
}

export function ProductCardHeader({ categoria, emEstoque, totalEstoque }: ProductCardHeaderProps) {
  return (
    <div className="flex items-center justify-between gap-2 text-left">
      <span className="rounded-md bg-slate-100 border border-slate-200/80 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600">
        {categoria}
      </span>
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
          emEstoque
            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
            : "bg-amber-50 text-amber-700 border border-amber-200"
        }`}
      >
        <span
          className={`h-1.5 w-1.5 rounded-full ${emEstoque ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`}
        />
        {emEstoque ? `Em estoque (${totalEstoque} un)` : "Sem estoque"}
      </span>
    </div>
  );
}
