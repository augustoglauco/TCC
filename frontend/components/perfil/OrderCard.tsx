import type { Order } from "@/lib/api/orders";

export function OrderCard({ order }: { order: Order }) {
  const formattedDate = new Date(order.criado_em).toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 shadow-2xs hover:border-slate-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-slate-800">
            Pedido #{order.id.slice(0, 8)}...
          </span>
          <span className="rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider">
            {order.status}
          </span>
        </div>
        <p className="text-xs text-slate-500">Realizado em {formattedDate}</p>
        <p className="text-xs text-slate-600">
          {order.itens.length} {order.itens.length === 1 ? "item" : "itens"}
          {order.itens.length > 0 && order.itens[0].nome_produto && (
            <span>
              :{" "}
              {order.itens
                .map((i) => i.nome_produto)
                .filter(Boolean)
                .join(", ")}
            </span>
          )}
        </p>
      </div>
      <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center border-t sm:border-t-0 pt-2 sm:pt-0 border-slate-100">
        <span className="text-xs text-slate-500">Total</span>
        <span className="text-base font-bold text-slate-900">
          R$ {Number(order.valor_total).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
        </span>
      </div>
    </div>
  );
}
