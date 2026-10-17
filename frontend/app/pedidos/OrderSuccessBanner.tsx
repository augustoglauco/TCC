"use client";

import Link from "next/link";

interface Props {
  orderId: string;
  onDismiss: () => void;
}

export function OrderSuccessBanner({ orderId, onDismiss }: Props) {
  return (
    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-6 space-y-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 text-xl font-bold">
          ✓
        </div>
        <div>
          <h3 className="text-lg font-bold text-emerald-900">Pedido Reservado com Sucesso!</h3>
          <p className="text-sm text-emerald-700 mt-1">
            Seu pedido foi registrado no sistema com status{" "}
            <span className="font-semibold text-emerald-900">&quot;reservado&quot;</span> e a
            reserva do estoque no Centro de Distribuição foi efetuada.
          </p>
          <div className="mt-3 flex items-center gap-2 font-mono text-xs font-bold bg-white border border-emerald-200 text-emerald-900 px-3 py-1.5 rounded-md w-fit">
            <span>ID do Pedido: {orderId}</span>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 pt-2">
        <Link
          href="/pedidos/historico"
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors"
        >
          <span>Ver no Histórico de Pedidos</span> &rarr;
        </Link>
        <button
          type="button"
          onClick={onDismiss}
          className="text-xs text-emerald-700 hover:text-emerald-900 underline font-medium cursor-pointer"
        >
          Realizar Novo Pedido
        </button>
      </div>
    </div>
  );
}
