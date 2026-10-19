"use client";

import { Suspense } from "react";
import { CartTab } from "./CartTab";
import { B2bQuoteTab } from "./B2bQuoteTab";
import { LoginRequired } from "./LoginRequired";
import { OrderSuccessBanner } from "./OrderSuccessBanner";
import { PedidosHeader } from "./PedidosHeader";
import { PedidosTabs } from "./PedidosTabs";
import { usePedidosPage } from "./usePedidosPage";

function PedidosPageContent() {
  const p = usePedidosPage();

  if (!p.currentUser) return <LoginRequired />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-12 space-y-8">
      <PedidosHeader />

      <PedidosTabs
        activeTab={p.activeTab}
        cartCount={p.cartItems.length}
        onChange={p.setActiveTab}
      />

      {p.completedOrderId && (
        <OrderSuccessBanner
          orderId={p.completedOrderId}
          onDismiss={() => p.setCompletedOrderId(null)}
        />
      )}

      {p.activeTab === "carrinho" && (
        <CartTab
          currentUser={p.currentUser}
          freightResult={p.freightResult}
          isCalculatingFreight={p.isCalculatingFreight}
          isSubmittingOrder={p.isSubmittingOrder}
          checkoutError={p.checkoutError}
          cep={p.cep}
          onCepChange={p.setCep}
          onCalcFreight={p.handleCalcFreight}
          onCheckout={p.handleCheckout}
        />
      )}
      {p.activeTab === "cotacao_b2b" && (
        <B2bQuoteTab
          catalogProducts={p.catalogProducts}
          selectedProdId={p.selectedProdId}
          simQuantity={p.simQuantity}
          simCd={p.simCd}
          simResult={p.simResult}
          isSimulating={p.isSimulating}
          simError={p.simError}
          onProdChange={p.setSelectedProdId}
          onQuantityChange={p.setSimQuantity}
          onCdChange={p.setSimCd}
          onSimulate={p.handleSimulateQuote}
          onAddToCart={p.handleAddQuotedToCart}
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
