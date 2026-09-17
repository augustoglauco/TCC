import Link from "next/link";

// MVP: histórico de pedidos ilustrativo (ver docs/ROADMAP.md, Fase 7)
const SAMPLE_ORDERS = [
  {
    id: "PED-9821",
    date: "14/09/2026",
    items: "2x Bomba Centrífuga Industrial 5HP",
    total: "R$ 8.500,00",
    status: "Em transporte",
    statusColor: "bg-blue-50 text-blue-700 border-blue-200",
  },
  {
    id: "PED-9540",
    date: "02/09/2026",
    items: "5x Válvula Esférica Inox 2\"",
    total: "R$ 1.900,00",
    status: "Entregue",
    statusColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
];

export default function PedidosPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho da página */}
      <div className="border-b border-slate-200 pb-6">
        <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
          <span>🛒</span> Gerenciamento de Pedidos
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
          Meus Pedidos & Orçamentos
        </h1>
        <p className="mt-2 text-sm text-slate-600">
          Acompanhe o status de entregas, cotações aprovadas ou consulte pedidos via Chat.
        </p>
      </div>

      {/* Tabela / Cards de Pedidos */}
      <div className="space-y-4">
        {SAMPLE_ORDERS.map((order) => (
          <div
            key={order.id}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-5 shadow-xs transition-all hover:border-slate-300"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <span className="font-mono font-bold text-slate-900 text-base">{order.id}</span>
                <span className="text-xs text-slate-500">Realizado em {order.date}</span>
              </div>
              <p className="text-sm font-medium text-slate-700">{order.items}</p>
            </div>

            <div className="flex items-center justify-between sm:justify-end gap-4 border-t border-slate-100 sm:border-t-0 pt-3 sm:pt-0">
              <span className="text-base font-bold text-slate-900">{order.total}</span>
              <span
                className={`rounded-full border px-3 py-1 text-xs font-semibold ${order.statusColor}`}
              >
                {order.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
