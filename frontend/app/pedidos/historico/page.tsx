"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchOrders, Order } from "@/lib/api/orders";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

export default function HistoricoPedidosPage() {
  const currentUser = useAuthStore((state) => state.user);
  const [orders, setOrders] = useState<Order[]>([]);
  const [filterEmail, setFilterEmail] = useState<string | null>(null);
  const userEmail = filterEmail !== null ? filterEmail : (currentUser?.email ?? "");
  const setUserEmail = (val: string) => setFilterEmail(val);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = async (emailToFilter?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchOrders({
        userEmail: emailToFilter?.trim() || undefined,
        limit: 50,
      });
      setOrders(res.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar histórico de pedidos.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadOrders(currentUser?.email || undefined);
  }, [currentUser?.email]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadOrders(userEmail);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            <span>📜</span> Consulta de Pedidos & Reservas
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Histórico de Pedidos
          </h1>
          <p className="mt-2 text-sm text-slate-600">
            Consulte seus pedidos realizados pelo site, simulações B2B ou reservadas via assistente
            no Chat.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/pedidos"
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            <span>🛒 Ir para o Carrinho</span>
          </Link>
        </div>
      </div>

      {/* Filtro por E-mail */}
      <div className="space-y-2">
        <form onSubmit={handleSearch} className="flex gap-2 max-w-md">
          <input
            type="email"
            placeholder="Filtrar por e-mail do cliente..."
            value={userEmail}
            onChange={(e) => setUserEmail(e.target.value)}
            className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="rounded-lg bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-900 transition-colors cursor-pointer"
          >
            Filtrar
          </button>
          {userEmail && (
            <button
              type="button"
              onClick={() => {
                setUserEmail("");
                loadOrders("");
              }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              Limpar
            </button>
          )}
        </form>
        {currentUser && userEmail === currentUser.email && (
          <p className="text-[11px] text-blue-600">
            ✓ Exibindo pedidos vinculados à sua conta (<strong>{currentUser.email}</strong>).
          </p>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
          {error}
        </div>
      )}

      {/* Conteúdo */}
      {isLoading ? (
        <div className="py-12 text-center text-xs text-slate-500">
          Carregando histórico de pedidos...
        </div>
      ) : orders.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 p-12 text-center space-y-3">
          <div className="text-3xl">📦</div>
          <h3 className="text-base font-bold text-slate-800">Nenhum pedido encontrado</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {userEmail
              ? `Nenhum pedido cadastrado para o e-mail "${userEmail}".`
              : "Ainda não existem pedidos cadastrados no sistema."}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <div
              key={order.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4 transition-all hover:border-slate-300"
            >
              {/* Topo do Card de Pedido */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-100 pb-3 gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded-md">
                      {order.id}
                    </span>
                    <span className="text-xs text-slate-500">
                      Realizado em {new Date(order.criado_em).toLocaleDateString("pt-BR")} às{" "}
                      {new Date(order.criado_em).toLocaleTimeString("pt-BR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  </div>
                  {order.user_email && (
                    <p className="text-xs text-slate-600 mt-1">
                      Cliente:{" "}
                      <span className="font-medium text-slate-800">{order.user_email}</span>
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-3">
                  <span className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 capitalize">
                    ● {order.status}
                  </span>
                  <span className="text-base font-bold text-slate-900">
                    R${" "}
                    {Number(order.valor_total).toLocaleString("pt-BR", {
                      minimumFractionDigits: 2,
                    })}
                  </span>
                </div>
              </div>

              {/* Tabela de Itens do Pedido */}
              <div className="space-y-2">
                <h5 className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Itens do Pedido ({order.itens.length})
                </h5>
                <div className="divide-y divide-slate-100 text-xs">
                  {order.itens.map((item) => (
                    <div
                      key={item.id || item.produto_id}
                      className="py-2 flex justify-between items-center"
                    >
                      <div>
                        <span className="font-semibold text-slate-900">
                          {item.nome_produto || `Produto #${item.produto_id}`}
                        </span>
                        <div className="flex items-center gap-2 text-slate-500 text-[11px] mt-0.5">
                          <span>{item.quantidade}x unidades</span>
                          <span>•</span>
                          <span>CD: {item.centro_distribuicao}</span>
                        </div>
                      </div>

                      <div className="text-right">
                        <span className="font-medium text-slate-900">
                          R${" "}
                          {Number(item.subtotal).toLocaleString("pt-BR", {
                            minimumFractionDigits: 2,
                          })}
                        </span>
                        <span className="block text-[10px] text-slate-400">
                          (R${" "}
                          {Number(item.preco_unitario).toLocaleString("pt-BR", {
                            minimumFractionDigits: 2,
                          })}{" "}
                          / un)
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
