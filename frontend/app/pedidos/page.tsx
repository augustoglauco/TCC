"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { CartTab } from "./CartTab";
import { B2bQuoteTab } from "./B2bQuoteTab";
import { OrderSuccessBanner } from "./OrderSuccessBanner";
import { PedidosTabs } from "./PedidosTabs";
import { usePedidosPage } from "./usePedidosPage";

function PedidosPageContent() {
  const {
    currentUser,
    cartItems,
    activeTab,
    setActiveTab,
    cep,
    setCep,
    freightResult,
    isCalculatingFreight,
    isSubmittingOrder,
    checkoutError,
    completedOrderId,
    setCompletedOrderId,
    catalogProducts,
    selectedProdId,
    setSelectedProdId,
    simQuantity,
    setSimQuantity,
    simCd,
    setSimCd,
    simResult,
    isSimulating,
    simError,
    handleCalcFreight,
    handleCheckout,
    handleSimulateQuote,
    handleAddQuotedToCart,
  } = usePedidosPage();

  if (!currentUser) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 text-3xl font-bold shadow-xs border border-amber-200">
          🔐
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Autenticação Necessária</h1>
          <p className="mt-2 text-sm text-slate-600">
            Para entrar em pedidos, acessar seu carrinho e finalizar compras, é necessário estar
            logado na sua conta.
          </p>
        </div>
        <div className="flex flex-col gap-3 pt-2">
          <Link
            href="/conta/login?redirect=/pedidos"
            className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            Entrar na Conta &rarr;
          </Link>
          <Link
            href="/produtos"
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Voltar para o Catálogo de Produtos
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Pedidos, Frete &amp; Preços Diferenciados B2B
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Finalize sua compra como cliente final ou simule descontos por volume para parceiros
            B2B.
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

      {/* Abas */}
      <PedidosTabs activeTab={activeTab} cartCount={cartItems.length} onChange={setActiveTab} />

      {completedOrderId && (
        <OrderSuccessBanner
          orderId={completedOrderId}
          onDismiss={() => setCompletedOrderId(null)}
        />
      )}

      {activeTab === "carrinho" && (
        <CartTab
          currentUser={currentUser}
          freightResult={freightResult}
          isCalculatingFreight={isCalculatingFreight}
          isSubmittingOrder={isSubmittingOrder}
          checkoutError={checkoutError}
          cep={cep}
          onCepChange={setCep}
          onCalcFreight={handleCalcFreight}
          onCheckout={handleCheckout}
        />
      )}

      {activeTab === "cotacao_b2b" && (
        <B2bQuoteTab
          catalogProducts={catalogProducts}
          selectedProdId={selectedProdId}
          simQuantity={simQuantity}
          simCd={simCd}
          simResult={simResult}
          isSimulating={isSimulating}
          simError={simError}
          onProdChange={setSelectedProdId}
          onQuantityChange={setSimQuantity}
          onCdChange={setSimCd}
          onSimulate={handleSimulateQuote}
          onAddToCart={handleAddQuotedToCart}
        />
      )}
    </div>
  );
}

export default function PedidosPage() {
  return (
    <Suspense
      fallback={<div className="py-12 text-center text-xs text-slate-500">Carregando...</div>}
    >
      <PedidosPageContent />
    </Suspense>
  );
}
