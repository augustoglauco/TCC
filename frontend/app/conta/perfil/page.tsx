"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { useRecentOrders } from "@/lib/hooks/useRecentOrders";
import {
  ChatCard,
  OrdersSection,
  PerfilAcessoRestrito,
  PerfilCabecalho,
  UserCard,
} from "@/components/perfil/PerfilSections";

export default function PerfilPage() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const openChat = useChatStore((state) => state.open);

  const isAdmin = user?.perfil?.toLowerCase() === "admin";
  const ordersState = useRecentOrders(user?.email, !isAdmin);

  const handleLogout = () => {
    logout();
    router.push("/conta/login");
  };

  if (!user) return <PerfilAcessoRestrito />;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10 sm:py-12 space-y-8">
      <PerfilCabecalho onLogout={handleLogout} />
      <UserCard user={user} isAdmin={isAdmin} />
      <ChatCard onOpenChat={openChat} />
      {!isAdmin && <OrdersSection {...ordersState} />}
    </div>
  );
}
