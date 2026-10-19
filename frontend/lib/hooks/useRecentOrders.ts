import { useEffect, useState } from "react";

import { fetchOrders, Order } from "@/lib/api/orders";

export function useRecentOrders(email: string | undefined, enabled: boolean) {
  const [orders, setOrders] = useState<Order[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [ordersError, setOrdersError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (email && enabled) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setIsLoadingOrders(true);
      setOrdersError(null);
      fetchOrders({ userEmail: email, limit: 10 })
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
  }, [email, enabled]);

  return { orders, isLoadingOrders, ordersError };
}
