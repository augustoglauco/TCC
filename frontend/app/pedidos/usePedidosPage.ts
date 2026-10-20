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

function useProdutoDaUrl(produtoParam: string | null) {
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
}

type ItemCarrinho = ReturnType<typeof useCartStore.getState>["items"][number];
type UsuarioLogado = ReturnType<typeof useAuthStore.getState>["user"];
type DefinirErro = (msg: string | null) => void;

const itensDoPedido = (cartItems: ItemCarrinho[]) =>
  cartItems.map((item) => ({
    produto_id: item.produtoId,
    quantidade: item.quantidade,
    centro_distribuicao: item.centroDistribuicao,
  }));

const mensagemDe = (err: unknown, padrao: string) => (err instanceof Error ? err.message : padrao);

function useFrete(cartItems: ItemCarrinho[], setCheckoutError: DefinirErro) {
  const [cep, setCep] = useState("");
  const [freightResult, setFreightResult] = useState<FreightQuoteResult | null>(null);
  const [isCalculatingFreight, setIsCalculatingFreight] = useState(false);

  const handleCalcFreight = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cep || cep.length < 8 || cartItems.length === 0) return;
    setIsCalculatingFreight(true);
    setCheckoutError(null);
    try {
      setFreightResult(await calculateFreight({ cep, itens: itensDoPedido(cartItems) }));
    } catch (err: unknown) {
      setCheckoutError(mensagemDe(err, "Erro ao calcular frete."));
    } finally {
      setIsCalculatingFreight(false);
    }
  };

  return { cep, setCep, freightResult, isCalculatingFreight, handleCalcFreight };
}

function useFinalizarPedido(
  currentUser: UsuarioLogado,
  cartItems: ItemCarrinho[],
  setCheckoutError: DefinirErro,
) {
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [completedOrderId, setCompletedOrderId] = useState<string | null>(null);

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
        itens: itensDoPedido(cartItems),
      });
      setCompletedOrderId(order.id);
      useCartStore.getState().clearCart();
    } catch (err: unknown) {
      setCheckoutError(mensagemDe(err, "Falha ao processar pedido."));
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  return { isSubmittingOrder, completedOrderId, setCompletedOrderId, handleCheckout };
}

function useCheckout() {
  const currentUser = useAuthStore((state) => state.user);
  const cartItems = useCartStore((state) => state.items);
  const [checkoutError, setCheckoutError] = useState<string | null>(null);

  const frete = useFrete(cartItems, setCheckoutError);
  const pedido = useFinalizarPedido(currentUser, cartItems, setCheckoutError);

  return { currentUser, cartItems, checkoutError, ...frete, ...pedido };
}

function useCatalogoCotavel() {
  const [catalogProducts, setCatalogProducts] = useState<Produto[]>([]);
  const [selectedProdId, setSelectedProdId] = useState<number | null>(null);

  useEffect(() => {
    fetchProducts({ limit: 50 })
      .then((res) => {
        setCatalogProducts(res.items);
        if (res.items.length > 0) setSelectedProdId(res.items[0].id);
      })
      .catch(() => {});
  }, []);

  return { catalogProducts, selectedProdId, setSelectedProdId };
}

function useSimulacaoCotacao(selectedProdId: number | null) {
  const [simQuantity, setSimQuantity] = useState<number>(10);
  const [simCd, setSimCd] = useState<string>("CD-SP");
  const [simResult, setSimResult] = useState<QuoteSimulationResult | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);

  const handleSimulateQuote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedProdId || simQuantity <= 0) return;
    setIsSimulating(true);
    setSimError(null);
    try {
      const itens = [
        { produto_id: selectedProdId, quantidade: simQuantity, centro_distribuicao: simCd },
      ];
      setSimResult(await calculateQuote({ itens }));
    } catch (err: unknown) {
      setSimError(mensagemDe(err, "Erro ao simular cotação."));
    } finally {
      setIsSimulating(false);
    }
  };

  return {
    simQuantity,
    setSimQuantity,
    simCd,
    setSimCd,
    simResult,
    isSimulating,
    simError,
    handleSimulateQuote,
  };
}

function useCotacaoB2b(onAddedToCart: () => void) {
  const catalogo = useCatalogoCotavel();
  const simulacao = useSimulacaoCotacao(catalogo.selectedProdId);
  const { catalogProducts, selectedProdId } = catalogo;
  const { simResult, simQuantity, simCd } = simulacao;

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
    onAddedToCart();
  };

  return { ...catalogo, ...simulacao, handleAddQuotedToCart };
}

export function usePedidosPage() {
  const searchParams = useSearchParams();
  useProdutoDaUrl(searchParams.get("produto"));

  const [activeTab, setActiveTab] = useState<"carrinho" | "cotacao_b2b">("carrinho");
  const checkout = useCheckout();
  const cotacao = useCotacaoB2b(() => setActiveTab("carrinho"));

  return { ...checkout, ...cotacao, activeTab, setActiveTab };
}
