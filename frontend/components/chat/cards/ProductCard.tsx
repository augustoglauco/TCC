"use client";

import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";
import type { ChatCardProduto } from "@/lib/types/chat";
import { formatarPrecoBRL } from "@/lib/utils/formatCurrency";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";

/** Card rico de produto (Fase 8) — resultado de Vendas sem quantidade
 * informada (sem cotação, ver `QuoteCard` nesse caso). */
export default function ProductCard({ card }: { card: ChatCardProduto }) {
  const imagemUrl = resolveImageUrl(card.imagem_url);
  const emEstoque = card.estoque_total > 0;

  // O `ChatWidget` fica no layout raiz, então o modal sobrevive à navegação do
  // `Link` e cobriria a página do produto — fecha ao clicar (mesmo padrão do
  // `ChatChartCard`).
  const fecharChat = () => useChatStore.getState().close();

  return (
    <Link
      href={`/produtos/${card.produto_id}`}
      onClick={fecharChat}
      className="flex w-full max-w-[85%] gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-xs transition-colors hover:border-blue-300 hover:bg-blue-50/30"
    >
      <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100">
        {imagemUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imagemUrl} alt={card.nome} className="h-full w-full object-cover" />
        ) : (
          <span className="text-2xl">📦</span>
        )}
      </div>
      <div className="flex min-w-0 flex-1 flex-col justify-center gap-0.5">
        <p className="truncate text-sm font-semibold text-slate-900">{card.nome}</p>
        <p className="text-sm font-bold text-blue-700">{formatarPrecoBRL(card.preco)}</p>
        <span
          className={`w-fit rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            emEstoque ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"
          }`}
        >
          {emEstoque ? `${card.estoque_total} em estoque` : "Sem estoque"}
        </span>
      </div>
    </Link>
  );
}
