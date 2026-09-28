"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { fetchOrders, Order } from "@/lib/api/orders";

export default function PerfilPage() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const openChat = useChatStore((state) => state.open);

  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (user?.email) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoadingOrders(true);
      setOrdersError(null);
      fetchOrders({ userEmail: user.email, limit: 10 })
        .then((res) => {
          if (isMounted) {
            setOrders(res.items);
          }
        })
        .catch((err: unknown) => {
          if (isMounted) {
            setOrdersError(
              err instanceof Error ? err.message : "Erro ao carregar histórico de pedidos.",
            );
          }
        })
        .finally(() => {
          if (isMounted) {
            setIsLoadingOrders(false);
          }
        });
    }
    return () => {
      isMounted = false;
    };
  }, [user?.email]);

  const handleLogout = () => {
    logout();
    router.push("/conta/login");
  };

  // Se o usuário não estiver autenticado
  if (!user) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center space-y-6">
        <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-slate-500 text-3xl font-bold shadow-2xs">
          🔒
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Acesso Restrito</h1>
          <p className="mt-2 text-sm text-slate-600">
            Você não está conectado. Faça login para acessar seus dados de perfil, pedidos e
            histórico personalizado.
          </p>
        </div>

        <div>
          <Link
            href="/conta/login"
            className="inline-flex items-center justify-center rounded-xl bg-blue-600 px-6 py-2.5 text-sm font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors"
          >
            <span>Ir para o Login</span> &rarr;
          </Link>
        </div>
      </div>
    );
  }

  const getProfileBadge = (perfil: string) => {
    const p = perfil.toLowerCase();
    if (p.includes("cliente")) {
      return {
        label: "Cliente VIP / Recorrente",
        classes: "bg-emerald-50 text-emerald-700 border-emerald-200",
        icon: "⭐",
      };
    }
    if (p.includes("esporádico") || p.includes("esporadico")) {
      return {
        label: "Cliente Esporádico",
        classes: "bg-blue-50 text-blue-700 border-blue-200",
        icon: "🏷️",
      };
    }
    return {
      label: "Lead Promissor",
      classes: "bg-purple-50 text-purple-700 border-purple-200",
      icon: "🎯",
    };
  };

  const badge = getProfileBadge(user.perfil);

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:py-12 space-y-8">
      {/* Cabeçalho */}
      <div className="border-b border-slate-200 pb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            <span>👤</span> Minha Conta
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Perfil do Usuário
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Informações cadastrais, classificação de relacionamento e pedidos recentes.
          </p>
        </div>

        <button
          type="button"
          onClick={handleLogout}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-rose-50 hover:text-rose-700 hover:border-rose-200 transition-colors cursor-pointer self-start sm:self-auto"
        >
          Sair da Conta
        </button>
      </div>

      {/* Cartão de Detalhes do Usuário */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-600 text-white text-2xl font-black shadow-xs">
              {user.nome ? user.nome.charAt(0).toUpperCase() : "U"}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-xl font-bold text-slate-900">{user.nome}</h2>
                <span className="text-xs font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded-md">
                  #{user.id}
                </span>
              </div>
              <p className="text-sm font-mono text-slate-600 mt-0.5">{user.email}</p>
            </div>
          </div>

          <div>
            <div
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-1.5 text-xs font-bold ${badge.classes}`}
            >
              <span>{badge.icon}</span>
              <span>{badge.label}</span>
            </div>
          </div>
        </div>

        {user.perfil_motivo && (
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3.5 text-xs text-slate-600">
            <span className="font-semibold text-slate-800">Classificação do Relacionamento: </span>
            {user.perfil_motivo}
          </div>
        )}
      </div>

      {/* Cartão de Integração com o Chat */}
      <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50/70 to-indigo-50/40 p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">💬</span>
            <h3 className="text-sm font-bold text-blue-900">Assistente Virtual Inteligente</h3>
          </div>
          <button
            type="button"
            onClick={openChat}
            className="rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-blue-700 transition-colors cursor-pointer"
          >
            Abrir Chat
          </button>
        </div>
        <p className="text-xs text-blue-800 leading-relaxed">
          Sua conta está vinculada automaticamente ao chat de atendimento. Ao iniciar uma conversa,
          o assistente já reconhecerá seu histórico de compras, adaptará o tom de comunicação e
          agilizará consultas pós-venda sem solicitar seu e-mail repetidamente.
        </p>
      </div>

      {/* Seção de Pedidos Recentes */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-slate-900">Meus Pedidos & Reservas Recentes</h3>
          <Link
            href="/pedidos/historico"
            className="text-xs font-semibold text-blue-600 hover:text-blue-800 hover:underline"
          >
            Ver Histórico Completo &rarr;
          </Link>
        </div>

        {isLoadingOrders ? (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-xs text-slate-500">
            Carregando pedidos...
          </div>
        ) : ordersError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-700">
            {ordersError}
          </div>
        ) : orders.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center space-y-3">
            <span className="text-3xl block">📦</span>
            <p className="text-sm font-semibold text-slate-700">
              Nenhum pedido encontrado para seu e-mail.
            </p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Seus pedidos realizados pelo site, simulações B2B ou conversas no chat aparecerão
              aqui.
            </p>
            <div className="pt-2">
              <Link
                href="/pedidos"
                className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-700 transition-colors"
              >
                <span>Criar Novo Pedido / Cotação</span> &rarr;
              </Link>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {orders.map((order) => {
              const formattedDate = new Date(order.criado_em).toLocaleDateString("pt-BR", {
                day: "2-digit",
                month: "2-digit",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              });

              return (
                <div
                  key={order.id}
                  className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 shadow-2xs hover:border-slate-300 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-800">
                        Pedido #{order.id.slice(0, 8)}...
                      </span>
                      <span className="rounded-full bg-blue-100 text-blue-800 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider">
                        {order.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500">Realizado em {formattedDate}</p>
                    <p className="text-xs text-slate-600">
                      {order.itens.length} {order.itens.length === 1 ? "item" : "itens"}
                      {order.itens.length > 0 && order.itens[0].nome_produto && (
                        <span>
                          :{" "}
                          {order.itens
                            .map((i) => i.nome_produto)
                            .filter(Boolean)
                            .join(", ")}
                        </span>
                      )}
                    </p>
                  </div>

                  <div className="flex sm:flex-col items-center sm:items-end justify-between sm:justify-center border-t sm:border-t-0 pt-2 sm:pt-0 border-slate-100">
                    <span className="text-xs text-slate-500">Total</span>
                    <span className="text-base font-bold text-slate-900">
                      R${" "}
                      {Number(order.valor_total).toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
