import Link from "next/link";
import type { ChatCardCotacao } from "@/lib/types/chat";
import { formatarPrecoBRL } from "@/lib/utils/formatCurrency";

/** Card rico de cotação (Fase 8, R12) — produto + quantidade já calculados
 * pelo `SalesCatalogClient` (mesmo dado do bloco de texto do prompt). */
export default function QuoteCard({ card }: { card: ChatCardCotacao }) {
  const temDesconto = Number(card.percentual_desconto) > 0;

  return (
    <Link
      href={`/produtos/${card.produto_id}`}
      className="flex w-full max-w-[85%] flex-col gap-2 rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 shadow-xs transition-colors hover:border-emerald-300 hover:bg-emerald-50"
    >
      <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-emerald-700">
        <span>💰</span> Cotação
      </div>
      <p className="text-sm font-semibold text-slate-900">{card.nome}</p>
      <div className="flex items-center justify-between text-xs text-slate-600">
        <span>
          {card.quantidade} × {formatarPrecoBRL(card.preco_unitario)}
        </span>
        {temDesconto && (
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-700">
            {card.percentual_desconto}% off
          </span>
        )}
      </div>
      <p className="text-base font-bold text-emerald-800">
        Total: {formatarPrecoBRL(card.subtotal)}
      </p>
    </Link>
  );
}
