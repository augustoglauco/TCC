"use client";

import { useChatStore } from "@/lib/hooks/useChatStore";

// MVP: catálogo ilustrativo para demonstração (ver docs/ROADMAP.md, Fase 7)
const SAMPLE_PRODUCTS = [
  {
    id: "prod-1",
    name: "Bomba Centrífuga Industrial 5HP",
    category: "Equipamentos",
    sku: "BCI-500",
    price: "R$ 4.250,00",
    stock: "Em estoque (12 un)",
  },
  {
    id: "prod-2",
    name: "Válvula Esférica Inox 2 polegadas",
    category: "Válvulas & Tubulações",
    sku: "VEI-200",
    price: "R$ 380,00",
    stock: "Em estoque (45 un)",
  },
  {
    id: "prod-3",
    name: "Motor Elétrico Trifásico 10CV",
    category: "Motores & Elétrica",
    sku: "MET-1000",
    price: "R$ 6.890,00",
    stock: "Sob encomenda",
  },
];

export default function ProdutosPage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho da página */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            <span>📦</span> Catálogo de Produtos & Peças
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Produtos Industriais
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Consulte estoque, fichas técnicas ou solicite cotações em tempo real via Chat.
          </p>
        </div>

        {/* Input de busca visual */}
        <div className="w-full sm:w-72">
          <input
            type="text"
            placeholder="Buscar por nome, SKU ou categoria..."
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Grid de Produtos */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {SAMPLE_PRODUCTS.map((prod) => (
          <div
            key={prod.id}
            className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:-translate-y-1 hover:border-blue-300 hover:shadow-md"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                  {prod.category}
                </span>
                <span className="text-[11px] font-mono text-slate-400">SKU: {prod.sku}</span>
              </div>
              <h3 className="mt-3 font-bold text-slate-900 text-base">{prod.name}</h3>
              <div className="mt-4 flex items-baseline justify-between">
                <span className="text-lg font-extrabold text-blue-700">{prod.price}</span>
                <span className="text-xs font-medium text-emerald-600">{prod.stock}</span>
              </div>
            </div>

            <div className="mt-5 border-t border-slate-100 pt-3">
              <button
                type="button"
                onClick={() => useChatStore.getState().open()}
                className="flex items-center justify-center gap-1.5 w-full rounded-lg border border-slate-200 bg-slate-50 py-2 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors cursor-pointer"
              >
                <span>Cotar via Chat</span>
                <span>💬</span>
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

