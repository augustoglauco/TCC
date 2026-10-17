"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import {
  createOrder,
  calculateFreight,
  calculateQuote,
  FreightQuoteResult,
  QuoteSimulationResult,
} from "@/lib/api/orders";
import { fetchProducts, fetchProductById, Produto } from "@/lib/api/products";
import { CartTab } from "./CartTab";
import { B2bQuoteTab } from "./B2bQuoteTab";
import { OrderSuccessBanner } from "./OrderSuccessBanner";

function PedidosPageContent() {
  const searchParams = useSearchParams();
  const produtoParam = searchParams.get("produto");

  const [activeTab, setActiveTab] = useState<"carrinho" | "cotacao_b2b">("carrinho");

  const currentUser = useAuthStore((state) => state.user);

  const cartItems = useCartStore((state) => state.items);

  // Form states checkout
  const [cep, setCep] = useState("");
  const [freightResult, setFreightResult] = useState<FreightQuoteResult | null>(null);
  const [isCalculatingFreight, setIsCalculatingFreight] = useState(false);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [completedOrderId, setCompletedOrderId] = useState<string | null>(null);

  // B2B Quote Simulator states
  const [catalogProducts, setCatalogProducts] = useState<Produto[]>([]);
  const [selectedProdId, setSelectedProdId] = useState<number | null>(null);
  const [simQuantity, setSimQuantity] = useState<number>(10);
  const [simCd, setSimCd] = useState<string>("CD-SP");
  const [simResult, setSimResult] = useState<QuoteSimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    if (produtoParam) {
      const pId = Number.parseInt(produtoParam, 10);
      if (!Number.isNaN(pId)) {
        fetchProductById(pId)
          .then((prod) => {
            const cd =
              prod.estoques && prod.estoques.length > 0
                ? prod.estoques.find((e) => e.quantidade > 0)?.centro_distribuicao ||
                  prod.estoques[0].centro_distribuicao
                : "CD-SP";
            const precoEfetivo = prod.preco_promocional || prod.preco;
            useCartStore.getState().addItem({
              produtoId: prod.id,
              nome: prod.nome,
              preco: Number(precoEfetivo),
              imagemUrl: prod.imagem_url,
              quantidade: 1,
              centroDistribuicao: cd,
            });
          })
          .catch(() => {});
      }
    }
  }, [produtoParam]);

  useEffect(() => {
    fetchProducts({ limit: 50 })
      .then((res) => {
        setCatalogProducts(res.items);
        if (res.items.length > 0) setSelectedProdId(res.items[0].id);
      })
      .catch(() => {});
  }, []);

  const handleCalcFreight = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cep || cep.length < 8 || cartItems.length === 0) return;
    setIsCalculatingFreight(true);
    setCheckoutError(null);
    try {
      const res = await calculateFreight({
        cep,
        itens: cartItems.map((item) => ({
          produto_id: item.produtoId,
          quantidade: item.quantidade,
          centro_distribuicao: item.centroDistribuicao,
        })),
      });
      setFreightResult(res);
    } catch (err: unknown) {
      setCheckoutError(err instanceof Error ? err.message : "Erro ao calcular frete.");
    } finally {
      setIsCalculatingFreight(false);
    }
  };

  const handleCheckout = async () => {
    if (!currentUser?.email) {
      setCheckoutError("É necessário estar logado para finalizar o pedido.");
      return;
    }
    if (cartItems.length === 0) return;
    setIsSubmittingOrder(true);
    setCheckoutError(null);
    try {
      const order = await createOrder({
        user_email: currentUser.email,
        conversation_id: useChatStore.getState().conversationId || undefined,
        itens: cartItems.map((item) => ({
          produto_id: item.produtoId,
          quantidade: item.quantidade,
          centro_distribuicao: item.centroDistribuicao,
        })),
      });
      setCompletedOrderId(order.id);
      useCartStore.getState().clearCart();
    } catch (err: unknown) {
      setCheckoutError(err instanceof Error ? err.message : "Falha ao processar pedido.");
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  const handleSimulateQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProdId || simQuantity <= 0) return;
    setIsSimulating(true);
    setSimError(null);
    try {
      const res = await calculateQuote({
        itens: [
          { produto_id: selectedProdId, quantidade: simQuantity, centro_distribuicao: simCd },
        ],
      });
      setSimResult(res);
    } catch (err: unknown) {
      setSimError(err instanceof Error ? err.message : "Erro ao simular cotação.");
    } finally {
      setIsSimulating(false);
    }
  };

  const handleAddQuotedToCart = () => {
    if (!selectedProdId || !simResult || simResult.itens.length === 0) return;
    const prod = catalogProducts.find((p) => p.id === selectedProdId);
    if (!prod) return;
    useCartStore.getState().addItem({
      produtoId: prod.id,
      nome: prod.nome,
      preco: Number(simResult.itens[0].preco_unitario_base),
      imagemUrl: prod.imagem_url,
      quantidade: simQuantity,
      centroDistribuicao: simCd,
    });
    setActiveTab("carrinho");
  };

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
      <div className="flex border-b border-slate-200 gap-4">
        <button
          type="button"
          onClick={() => setActiveTab("carrinho")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "carrinho"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>🛒 Meu Carrinho &amp; Checkout</span>
          {cartItems.length > 0 && (
            <span className="rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-xs font-bold">
              {cartItems.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("cotacao_b2b")}
          className={`pb-3 text-sm font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
            activeTab === "cotacao_b2b"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <span>🏢 Simulador B2B (Preços por Volume)</span>
        </button>
      </div>

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
