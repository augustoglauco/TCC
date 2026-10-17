"use client";

import Link from "next/link";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { FreightQuoteResult } from "@/lib/api/orders";

interface CartTabProps {
  currentUser: { nome: string; email: string; perfil?: string };
  freightResult: FreightQuoteResult | null;
  isCalculatingFreight: boolean;
  isSubmittingOrder: boolean;
  checkoutError: string | null;
  cep: string;
  onCepChange: (v: string) => void;
  onCalcFreight: (e: React.FormEvent) => void;
  onCheckout: () => void;
}

export function CartTab({
  currentUser,
  freightResult,
  isCalculatingFreight,
  isSubmittingOrder,
  checkoutError,
  cep,
  onCepChange,
  onCalcFreight,
  onCheckout,
}: CartTabProps) {
  const cartItems = useCartStore((state) => state.items);
  const updateQuantity = useCartStore((state) => state.updateQuantity);
  const removeItem = useCartStore((state) => state.removeItem);
  const clearCart = useCartStore((state) => state.clearCart);
  const totalCartValue = useCartStore((state) => state.totalValue());

  if (cartItems.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center space-y-4">
        <div className="text-4xl">🛒</div>
        <h3 className="text-lg font-semibold text-slate-800">Seu carrinho está vazio</h3>
        <p className="text-sm text-slate-500 max-w-md mx-auto">
          Explore nosso catálogo de produtos ou consulte o assistente inteligente no chat para
          adicionar itens.
        </p>
        <Link
          href="/produtos"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-700 transition-colors"
        >
          <span>Ver Catálogo de Produtos</span> &rarr;
        </Link>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      {/* Lista de Itens */}
      <div className="lg:col-span-2 space-y-4">
        <div className="flex justify-between items-center pb-2">
          <h2 className="text-lg font-bold text-slate-900">
            Itens Selecionados ({cartItems.length})
          </h2>
          <button
            type="button"
            onClick={() => clearCart()}
            className="text-xs text-rose-600 hover:text-rose-800 font-medium cursor-pointer"
          >
            Esvaziar carrinho
          </button>
        </div>

        <div className="space-y-3">
          {cartItems.map((item) => (
            <div
              key={`${item.produtoId}-${item.centroDistribuicao}`}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white p-4 shadow-xs"
            >
              <div className="flex items-center gap-3">
                <div className="h-14 w-14 relative rounded-lg bg-slate-100 overflow-hidden border border-slate-200 shrink-0 flex items-center justify-center">
                  {item.imagemUrl ? (
                    // Mesmo padrão do ProductCard.tsx: a URL vem de um host dinâmico
                    // resolvido em runtime (ver getApiBaseUrl()), então next/image
                    // bloquearia por hostname não configurado em next.config.ts.
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={item.imagemUrl}
                      alt={item.nome}
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <span className="text-slate-400 text-xs font-bold">Foto</span>
                  )}
                </div>
                <div>
                  <h4 className="font-semibold text-slate-900 text-sm">{item.nome}</h4>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="rounded-md bg-slate-100 text-slate-700 px-2 py-0.5 text-[11px] font-semibold">
                      {item.centroDistribuicao}
                    </span>
                    <span className="text-xs text-slate-500">
                      R$ {item.preco.toLocaleString("pt-BR", { minimumFractionDigits: 2 })} / un
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-4">
                <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50">
                  <button
                    type="button"
                    onClick={() =>
                      updateQuantity(item.produtoId, item.centroDistribuicao, item.quantidade - 1)
                    }
                    className="px-2.5 py-1 text-slate-600 hover:text-slate-900 font-bold cursor-pointer text-xs"
                  >
                    -
                  </button>
                  <span className="px-3 py-1 text-xs font-bold text-slate-900 bg-white border-x border-slate-200">
                    {item.quantidade}
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      updateQuantity(item.produtoId, item.centroDistribuicao, item.quantidade + 1)
                    }
                    className="px-2.5 py-1 text-slate-600 hover:text-slate-900 font-bold cursor-pointer text-xs"
                  >
                    +
                  </button>
                </div>

                <span className="text-sm font-bold text-slate-900 min-w-[90px] text-right">
                  R${" "}
                  {(item.preco * item.quantidade).toLocaleString("pt-BR", {
                    minimumFractionDigits: 2,
                  })}
                </span>

                <button
                  type="button"
                  onClick={() => removeItem(item.produtoId, item.centroDistribuicao)}
                  className="text-slate-400 hover:text-rose-600 p-1 transition-colors cursor-pointer text-sm"
                  title="Remover item"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Calculadora de Frete */}
        <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3 mt-6">
          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
            🚚 Simulador de Frete &amp; Entrega por CEP
          </h4>
          <form onSubmit={onCalcFreight} className="flex gap-2">
            <input
              type="text"
              placeholder="CEP ex: 01000-000"
              value={cep}
              onChange={(e) => onCepChange(e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500 flex-1 max-w-[200px]"
            />
            <button
              type="submit"
              disabled={isCalculatingFreight || !cep}
              className="rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-900 disabled:opacity-50 transition-colors cursor-pointer"
            >
              {isCalculatingFreight ? "Calculando..." : "Calcular Frete"}
            </button>
          </form>

          {freightResult && (
            <div className="mt-2 rounded-lg bg-white border border-slate-200 p-3 flex items-center justify-between text-xs">
              <div>
                <span className="font-semibold text-slate-800">Estimativa de Entrega:</span>{" "}
                <span className="text-slate-600">
                  {freightResult.prazo_dias} dias úteis ({freightResult.peso_total_kg} kg total)
                </span>
              </div>
              <span className="font-bold text-blue-700 text-sm">
                R${" "}
                {Number(freightResult.custo_estimado).toLocaleString("pt-BR", {
                  minimumFractionDigits: 2,
                })}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Resumo & Checkout */}
      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-6 shadow-xs">
          <h3 className="text-lg font-bold text-slate-900 border-b border-slate-100 pb-3">
            Resumo da Compra
          </h3>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between text-slate-600">
              <span>Subtotal dos produtos</span>
              <span className="font-semibold text-slate-900">
                R$ {totalCartValue.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </span>
            </div>

            <div className="flex justify-between text-slate-600">
              <span>Frete estimado</span>
              <span className="font-semibold text-slate-900">
                {freightResult
                  ? `R$ ${Number(freightResult.custo_estimado).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`
                  : "Calcular acima"}
              </span>
            </div>

            <div className="border-t border-slate-200 pt-3 flex justify-between items-center text-sm">
              <span className="font-bold text-slate-900">Total Geral</span>
              <span className="text-lg font-bold text-blue-700">
                R${" "}
                {(
                  totalCartValue + (freightResult ? Number(freightResult.custo_estimado) : 0)
                ).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          <div className="space-y-1.5 pt-2 border-t border-slate-100">
            <label className="text-xs font-semibold text-slate-700 block">
              Cliente Autenticado:
            </label>
            <div className="rounded-lg bg-blue-50/70 border border-blue-100 p-2.5 flex items-center justify-between text-xs">
              <div>
                <span className="font-bold text-slate-900 block">{currentUser.nome}</span>
                <span className="text-slate-500 font-mono text-[11px]">{currentUser.email}</span>
              </div>
              <span className="rounded bg-blue-100 text-blue-700 px-2 py-0.5 text-[10px] font-bold">
                {currentUser.perfil || "Cliente"}
              </span>
            </div>
          </div>

          {checkoutError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-700">
              {checkoutError}
            </div>
          )}

          <button
            type="button"
            onClick={onCheckout}
            disabled={isSubmittingOrder}
            className="w-full rounded-xl bg-blue-600 py-3 text-xs font-bold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer flex items-center justify-center gap-2"
          >
            {isSubmittingOrder ? (
              <span>Processando Reserva...</span>
            ) : (
              <>
                <span>Finalizar Pedido &amp; Reservar</span> &rarr;
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
