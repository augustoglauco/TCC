import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import PerfilPage from "@/app/conta/perfil/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import * as ordersApi from "@/lib/api/orders";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("PerfilPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza mensagem de acesso restrito quando o usuário não estiver logado", () => {
    render(<PerfilPage />);

    expect(screen.getByText("Acesso Restrito")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ir para o Login/i })).toBeInTheDocument();
  });

  it("renderiza dados do usuário autenticado e histórico de pedidos", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
        perfil_motivo: "3 compras recentes no histórico",
      },
      token: "mock-token",
    });

    const mockOrders = [
      {
        id: "order-abc-123",
        status: "reservado",
        criado_em: "2026-09-28T12:00:00Z",
        user_email: "ana.recorrente@example.com",
        valor_total: 890.5,
        itens: [
          {
            produto_id: 1,
            nome_produto: "Câmera Bullet IP",
            quantidade: 2,
            centro_distribuicao: "CD-SP",
            preco_unitario: 445.25,
            subtotal: 890.5,
          },
        ],
      },
    ];

    const fetchOrdersSpy = vi.spyOn(ordersApi, "fetchOrders").mockResolvedValue({
      items: mockOrders,
      total: 1,
      limit: 10,
      offset: 0,
    });

    render(<PerfilPage />);

    expect(screen.getByRole("heading", { name: "Perfil do Usuário" })).toBeInTheDocument();
    expect(screen.getByText("Ana Recorrente")).toBeInTheDocument();
    expect(screen.getByText("ana.recorrente@example.com")).toBeInTheDocument();
    expect(screen.getByText("Cliente VIP / Recorrente")).toBeInTheDocument();
    expect(screen.getByText(/3 compras recentes no histórico/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(fetchOrdersSpy).toHaveBeenCalledWith({
        userEmail: "ana.recorrente@example.com",
        limit: 10,
      });
      expect(screen.getByText(/Pedido #order-ab/i)).toBeInTheDocument();
      expect(screen.getByText("reservado")).toBeInTheDocument();
    });
  });

  it("permite deslogar ao clicar em 'Sair da Conta'", async () => {
    const mockLogout = vi.fn();
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
      logout: mockLogout,
    });

    vi.spyOn(ordersApi, "fetchOrders").mockResolvedValue({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    });

    render(<PerfilPage />);

    const logoutBtn = screen.getByRole("button", { name: "Sair da Conta" });
    fireEvent.click(logoutBtn);

    expect(mockLogout).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/conta/login");
  });

  it("abre o chat ao clicar no botão 'Abrir Chat'", () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    vi.spyOn(ordersApi, "fetchOrders").mockResolvedValue({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
    });

    useChatStore.setState({ isOpen: false });

    render(<PerfilPage />);

    const openChatBtn = screen.getByRole("button", { name: "Abrir Chat" });
    fireEvent.click(openChatBtn);

    expect(useChatStore.getState().isOpen).toBe(true);
  });
});
