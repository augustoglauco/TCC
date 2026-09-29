"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { fetchOrders, Order } from "@/lib/api/orders";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

function HistoricoPedidosContent() {
  const searchParams = useSearchParams();
  const targetEmailParam = searchParams.get("email");

  const currentUser = useAuthStore((state) => state.user);
  const isAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const targetEmail =
    isAdmin && targetEmailParam ? targetEmailParam.trim() : (currentUser?.email ?? "");
  const isAdminInspectingCustomer = isAdmin && Boolean(targetEmailParam) && targetEmailParam !== currentUser?.email;

  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadOrders = async (userEmail: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetchOrders({
        userEmail: userEmail.trim(),
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
    if (targetEmail) {
      loadOrders(targetEmail);
    } else {
      setIsLoading(false);
    }
  }, [targetEmail]);

  if (!currentUser) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 text-3xl font-bold shadow-xs border border-amber-200">
          📜
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Histórico Restrito ao Usuário</h1>
          <p className="mt-2 text-sm text-slate-600">
            Para consultar seu histórico de pedidos e cotações, faça login na sua conta.
          </p>
        </div>

        <div className="flex flex-col gap-3 pt-2">
          <Link
            href="/conta/login?redirect=/pedidos/historico"
            className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            Entrar na Conta &rarr;
          </Link>
          <Link
            href="/produtos"
            className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
          >
            Voltar ao Catálogo
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

      {/* Banner de Inspeção Administrativa ou Identificação de Usuário */}
      {isAdminInspectingCustomer ? (
        <div className="rounded-xl bg-purple-50 border border-purple-200 p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="text-2xl">⚙️</span>
            <div>
              <h4 className="text-xs font-bold text-purple-900 uppercase tracking-wider">
                Modo de Consulta Administrativa
              </h4>
              <p className="text-xs text-purple-700 mt-0.5">
                Exibindo histórico de pedidos do cliente: <strong className="font-mono text-purple-900">{targetEmail}</strong>
              </p>
            </div>
          </div>
          <Link
            href="/admin/usuarios"
            className="inline-flex items-center gap-1.5 rounded-lg bg-purple-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-purple-700 transition-colors shrink-0"
          >
            <span>&larr; Voltar para Gestão de Usuários</span>
          </Link>
        </div>
      ) : (
        <div className="rounded-xl bg-blue-50/70 border border-blue-100 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-xl">👤</span>
            <div>
              <h4 className="text-xs font-bold text-slate-900">
                Histórico de Pedidos de {currentUser.nome}
              </h4>
              <p className="text-[11px] text-blue-700 font-mono mt-0.5">
                Exibindo apenas pedidos vinculados a <strong>{currentUser.email}</strong>
              </p>
            </div>
          </div>
          <span className="rounded-full bg-blue-100 text-blue-800 px-3 py-1 text-xs font-semibold">
            {currentUser.perfil || "Cliente"}
          </span>
        </div>
      )}

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
            Nenhum pedido cadastrado para o e-mail &quot;{targetEmail}&quot;.
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

export default function HistoricoPedidosPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-5xl px-4 py-12 text-center text-xs text-slate-500">
          Carregando histórico...
        </div>
      }
    >
      <HistoricoPedidosContent />
    </Suspense>
  );
}

