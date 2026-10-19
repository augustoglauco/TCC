"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { fetchOrders, Order } from "@/lib/api/orders";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

export function useHistoricoPedidos() {
  const searchParams = useSearchParams();
  const targetEmailParam = searchParams.get("email");

  const currentUser = useAuthStore((state) => state.user);
  const isAdmin = currentUser?.perfil?.toLowerCase() === "admin";

  const targetEmail =
    isAdmin && targetEmailParam ? targetEmailParam.trim() : (currentUser?.email ?? "");
  const isAdminInspectingCustomer =
    isAdmin && Boolean(targetEmailParam) && targetEmailParam !== currentUser?.email;

  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Nao toca estado antes do primeiro `await`: este loader roda a partir de um
  // efeito, onde setState sincrono dispara render em cascata
  // (react-hooks/set-state-in-effect). Os caminhos interativos ligam o spinner
  // no proprio handler.
  const loadOrders = async (userEmail: string) => {
    try {
      const res = await fetchOrders({
        userEmail: userEmail.trim(),
        limit: 50,
      });
      setOrders(res.items);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao carregar histórico de pedidos.");
    } finally {
      setIsLoading(false);
    }
  };

  // Sem email alvo nao existe carga em curso: derivar substitui o
  // `else { setIsLoading(false) }` que rodava dentro do efeito.
  const carregando = isLoading && Boolean(targetEmail);

  useEffect(() => {
    if (!targetEmail) return;
    // Falso positivo: `loadOrders` so toca estado depois de `await fetchOrders`
    // (funcao `async` importada), logo nao ha setState sincrono aqui. A regra
    // nao resolve a assincronia da chamada e assume o pior caso.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadOrders(targetEmail);
  }, [targetEmail]);

  return { currentUser, targetEmail, isAdminInspectingCustomer, orders, carregando, error };
}
