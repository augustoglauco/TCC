"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import Image from "next/image";
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

function PedidosPageContent() {
  const searchParams = useSearchParams();
  const produtoParam = searchParams.get("produto");

  const [activeTab, setActiveTab] = useState<"carrinho" | "cotacao_b2b">("carrinho");

  // Auth Store
  const currentUser = useAuthStore((state) => state.user);

  // Cart Store
  const cartItems = useCartStore((state) => state.items);
  const updateQuantity = useCartStore((state) => state.updateQuantity);
  const removeItem = useCartStore((state) => state.removeItem);
  const clearCart = useCartStore((state) => state.clearCart);
  const totalCartValue = useCartStore((state) => state.totalValue());

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

  // Carrega produto por parâmetro de URL se acessado via /pedidos?produto=X
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

  // Carrega lista de produtos para o simulador B2B
  useEffect(() => {
    fetchProducts({ limit: 50 })
      .then((res) => {
        setCatalogProducts(res.items);
        if (res.items.length > 0) {
          setSelectedProdId(res.items[0].id);
        }
      })
      .catch(() => {});
  }, []);

  // Handler Cálculo de Frete
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

  // Handler Finalização de Pedido
  const handleCheckout = async () => {
    if (!currentUser || !currentUser.email) {
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
      clearCart();
    } catch (err: unknown) {
      setCheckoutError(err instanceof Error ? err.message : "Falha ao processar pedido.");
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // Handler Simulação B2B
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

  // Adicionar item cotado ao carrinho
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
            Para entrar em pedidos, acessar seu carrinho e finalizar compras, é necessário estar logado na sua conta.
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
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            <span>🛒</span> Workflow de Compras & Cotações
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Pedidos, Frete & Preços Diferenciados B2B
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
          <span>🛒 Meu Carrinho & Checkout</span>
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

      {/* MODAL / AVISO DE SUCESSO DE PEDIDO */}
      {completedOrderId && (
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
                <span>ID do Pedido: {completedOrderId}</span>
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
              onClick={() => setCompletedOrderId(null)}
              className="text-xs text-emerald-700 hover:text-emerald-900 underline font-medium cursor-pointer"
            >
              Realizar Novo Pedido
            </button>
          </div>
        </div>
      )}

      {/* ABA 1: CARRINHO E CHECKOUT */}
      {activeTab === "carrinho" && (
        <div className="space-y-6">
          {cartItems.length === 0 ? (
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
          ) : (
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
                            <Image
                              src={item.imagemUrl}
                              alt={item.nome}
                              fill
                              className="object-cover"
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
                              R$ {item.preco.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}{" "}
                              / un
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Controles de Quantidade */}
                      <div className="flex items-center justify-between sm:justify-end gap-4">
                        <div className="flex items-center rounded-lg border border-slate-200 bg-slate-50">
                          <button
                            type="button"
                            onClick={() =>
                              updateQuantity(
                                item.produtoId,
                                item.centroDistribuicao,
                                item.quantidade - 1,
                              )
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
                              updateQuantity(
                                item.produtoId,
                                item.centroDistribuicao,
                                item.quantidade + 1,
                              )
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

                {/* Calculadora de Frete por CEP */}
                <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3 mt-6">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    🚚 Simulador de Frete & Entrega por CEP
                  </h4>
                  <form onSubmit={handleCalcFreight} className="flex gap-2">
                    <input
                      type="text"
                      placeholder="CEP ex: 01000-000"
                      value={cep}
                      onChange={(e) => setCep(e.target.value)}
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
                          {freightResult.prazo_dias} dias úteis ({freightResult.peso_total_kg} kg
                          total)
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

              {/* Resumo do Pedido & Formulario Checkout */}
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
                          totalCartValue +
                          (freightResult ? Number(freightResult.custo_estimado) : 0)
                        ).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  {/* Informações do Cliente Autenticado */}
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
                    onClick={handleCheckout}
                    disabled={isSubmittingOrder}
                    className="w-full rounded-xl bg-blue-600 py-3 text-xs font-bold text-white shadow-xs hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer flex items-center justify-center gap-2"
                  >
                    {isSubmittingOrder ? (
                      <span>Processando Reserva...</span>
                    ) : (
                      <>
                        <span>Finalizar Pedido & Reservar</span> &rarr;
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ABA 2: SIMULADOR B2B DE PREÇOS POR VOLUME */}
      {activeTab === "cotacao_b2b" && (
        <div className="space-y-6">
          <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-6 space-y-4">
            <h3 className="text-lg font-bold text-slate-900">
              🏢 Cotador B2B de Preços Diferenciados
            </h3>
            <p className="text-xs text-slate-600">
              Simule a aplicação de políticas comerciais com faixas de desconto por quantidade
              mínima e precificação diferenciada B2B via API/MCP.
            </p>

            <form
              onSubmit={handleSimulateQuote}
              className="grid grid-cols-1 sm:grid-cols-4 gap-4 items-end pt-2"
            >
              <div className="sm:col-span-2 space-y-1">
                <label className="text-xs font-bold text-slate-700">Produto:</label>
                <select
                  value={selectedProdId || ""}
                  onChange={(e) => setSelectedProdId(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                >
                  {catalogProducts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.nome} (R${" "}
                      {Number(p.preco).toLocaleString("pt-BR", { minimumFractionDigits: 2 })})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Quantidade:</label>
                <input
                  type="number"
                  min="1"
                  value={simQuantity}
                  onChange={(e) => setSimQuantity(Number(e.target.value))}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-700">Centro de Distribuição:</label>
                <select
                  value={simCd}
                  onChange={(e) => setSimCd(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:ring-2 focus:ring-blue-500 focus:outline-hidden"
                >
                  <option value="CD-SP">CD-SP (São Paulo)</option>
                  <option value="CD-RJ">CD-RJ (Rio de Janeiro)</option>
                  <option value="CD-MG">CD-MG (Minas Gerais)</option>
                </select>
              </div>

              <div className="sm:col-span-4 flex justify-end">
                <button
                  type="submit"
                  disabled={isSimulating}
                  className="rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors cursor-pointer"
                >
                  {isSimulating ? "Calculando..." : "Simular Cotação B2B"}
                </button>
              </div>
            </form>
          </div>

          {simError && (
            <div className="rounded-lg bg-rose-50 border border-rose-200 p-4 text-xs text-rose-700">
              {simError}
            </div>
          )}

          {/* Resultado da Cotação B2B */}
          {simResult && simResult.itens.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 space-y-6 shadow-xs">
              <div className="flex justify-between items-center border-b border-slate-100 pb-4">
                <div>
                  <h4 className="font-bold text-slate-900 text-base">Resultado da Cotação B2B</h4>
                  <p className="text-xs text-slate-500">
                    Calculado via motor de precificação e desconto por volume.
                  </p>
                </div>
                <span className="rounded-full bg-blue-100 text-blue-800 px-3 py-1 text-xs font-bold">
                  {simResult.itens[0].percentual_desconto_aplicado}% de Desconto Aplicado
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
                  <span className="text-xs text-slate-500 block">Preço Unitário Base</span>
                  <span className="text-base font-bold text-slate-800">
                    R${" "}
                    {Number(simResult.itens[0].preco_unitario_base).toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>

                <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
                  <span className="text-xs text-blue-700 font-medium block">
                    Preço com Desconto de Volume
                  </span>
                  <span className="text-base font-bold text-blue-900">
                    R${" "}
                    {(
                      Number(simResult.itens[0].preco_unitario_base) *
                      (1 - Number(simResult.itens[0].percentual_desconto_aplicado) / 100)
                    ).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}
                  </span>
                </div>

                <div className="rounded-xl border border-emerald-100 bg-emerald-50/50 p-4">
                  <span className="text-xs text-emerald-700 font-medium block">
                    Valor Total Cotado
                  </span>
                  <span className="text-lg font-bold text-emerald-900">
                    R${" "}
                    {Number(simResult.valor_total).toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={handleAddQuotedToCart}
                  className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 transition-colors cursor-pointer"
                >
                  <span>Adicionar Cotação ao Carrinho</span> &rarr;
                </button>
              </div>
            </div>
          )}
        </div>
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
