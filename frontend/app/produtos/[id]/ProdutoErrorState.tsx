"use client";

import Link from "next/link";

interface ProdutoErrorStateProps {
  error: string | null;
}

export function ProdutoErrorState({ error }: ProdutoErrorStateProps) {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16 text-center">
      <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 text-3xl font-bold mb-4">
        ⚠️
      </div>
      <h1 className="text-2xl font-bold text-slate-900">
        {error?.includes("não encontrado") ? "Produto não encontrado" : "Erro ao carregar produto"}
      </h1>
      <p className="mt-2 text-sm text-slate-600 max-w-md mx-auto">
        {error || "O produto solicitado não foi localizado no catálogo da empresa."}
      </p>
      <div className="mt-6 flex items-center justify-center gap-3">
        <Link
          href="/produtos"
          className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
        >
          ← Voltar ao Catálogo
        </Link>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs sm:text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors cursor-pointer"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  );
}
