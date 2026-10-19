"use client";

import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";

export function PedidosHeader() {
  return (
    <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Pedidos, Frete &amp; Preços Diferenciados B2B
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Finalize sua compra como cliente final ou simule descontos por volume para parceiros B2B.
        </p>
      </div>
      <div className="flex items-center gap-2">
        <Link
          href="/pedidos/historico"
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-xs font-semibold text-slate-700 shadow-xs hover:bg-slate-50 transition-colors"
        >
          <span>📜 Histórico de Pedidos</span>
        </Link>
        <button
          type="button"
          onClick={() => useChatStore.getState().open()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors cursor-pointer"
        >
          <span>Cotar no Chat</span> 💬
        </button>
      </div>
    </div>
  );
}
