"use client";

import { useState, useEffect } from "react";
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

export function usePedidosPage() {
  const searchParams = useSearchParams();
  const produtoParam = searchParams.get("produto");

  const currentUser = useAuthStore((state) => state.user);
  const cartItems = useCartStore((state) => state.items);

  const [activeTab, setActiveTab] = useState<"carrinho" | "cotacao_b2b">("carrinho");

  // Checkout state
  const [cep, setCep] = useState("");
  const [freightResult, setFreightResult] = useState<FreightQuoteResult | null>(null);
  const [isCalculatingFreight, setIsCalculatingFreight] = useState(false);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);
  const [completedOrderId, setCompletedOrderId] = useState<string | null>(null);

  // B2B quote state
  const [catalogProducts, setCatalogProducts] = useState<Produto[]>([]);
  const [selectedProdId, setSelectedProdId] = useState<number | null>(null);
  const [simQuantity, setSimQuantity] = useState<number>(10);
  const [simCd, setSimCd] = useState<string>("CD-SP");
  const [simResult, setSimResult] = useState<QuoteSimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  useEffect(() => {
    if (!produtoParam) return;
    const pId = Number.parseInt(produtoParam, 10);
    if (Number.isNaN(pId)) return;
    fetchProductById(pId)
      .then((prod) => {
        const cd =
          prod.estoques && prod.estoques.length > 0
            ? prod.estoques.find((e) => e.quantidade > 0)?.centro_distribuicao ||
              prod.estoques[0].centro_distribuicao
            : "CD-SP";
        useCartStore.getState().addItem({
          produtoId: prod.id,
          nome: prod.nome,
          preco: Number(prod.preco_promocional || prod.preco),
          imagemUrl: prod.imagem_url,
          quantidade: 1,
          centroDistribuicao: cd,
        });
      })
      .catch(() => {});
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
        itens: [{ produto_id: selectedProdId, quantidade: simQuantity, centro_distribuicao: simCd }],
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

  return {
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
  };
}
