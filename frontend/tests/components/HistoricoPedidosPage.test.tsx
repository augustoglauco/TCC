import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import HistoricoPedidosPage from "@/app/pedidos/historico/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as ordersApi from "@/lib/api/orders";

let searchParamsEmail: string | null = null;

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({
    get: (param: string) => (param === "email" ? searchParamsEmail : null),
  }),
}));

describe("HistoricoPedidosPage", () => {
  beforeEach(() => {
    searchParamsEmail = null;
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza mensagem de autenticação necessária quando o usuário não estiver logado", async () => {
    render(<HistoricoPedidosPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Histórico Restrito ao Usuário" }),
      ).toBeInTheDocument();
      expect(
        screen.getByText(/Para consultar seu histórico de pedidos e cotações, faça login/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Entrar na Conta/i })).toBeInTheDocument();
    });
  });

  it("carrega e exibe estritamente o histórico de pedidos do usuário autenticado", async () => {
    const mockOrders = [
      {
        id: "ped-ana-100",
        status: "reservado",
        criado_em: "2026-09-29T08:00:00Z",
        user_email: "ana.recorrente@example.com",
        valor_total: 1200.0,
        itens: [
          {
            produto_id: 5,
            nome_produto: "Inversor Solar 5kW",
            quantidade: 1,
            centro_distribuicao: "CD-SP",
            preco_unitario: 1200.0,
            subtotal: 1200.0,
          },
        ],
      },
    ];

    const fetchOrdersSpy = vi.spyOn(ordersApi, "fetchOrders").mockResolvedValue({
      items: mockOrders,
      total: 1,
      limit: 50,
      offset: 0,
    });

    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    render(<HistoricoPedidosPage />);

    await waitFor(() => {
      expect(fetchOrdersSpy).toHaveBeenCalledWith({
        userEmail: "ana.recorrente@example.com",
        limit: 50,
      });
      expect(screen.getByText("ped-ana-100")).toBeInTheDocument();
      expect(screen.getByText("Inversor Solar 5kW")).toBeInTheDocument();
    });
  });

  it("carrega o histórico do usuário selecionado quando o administrador acessa via parâmetro ?email", async () => {
    searchParamsEmail = "cliente.parceiro@example.com";

    const mockAdminUser = {
      id: 99,
      nome: "Admin System",
      email: "admin@empresa.com",
      perfil: "Admin",
    };

    const mockOrders = [
      {
        id: "ped-parceiro-200",
        status: "aprovado",
        criado_em: "2026-09-29T09:00:00Z",
        user_email: "cliente.parceiro@example.com",
        valor_total: 5000.0,
        itens: [
          {
            produto_id: 10,
            nome_produto: "Módulo Fotovoltaico 550W",
            quantidade: 10,
            centro_distribuicao: "CD-MG",
            preco_unitario: 500.0,
            subtotal: 5000.0,
          },
        ],
      },
    ];

    const fetchOrdersSpy = vi.spyOn(ordersApi, "fetchOrders").mockResolvedValue({
      items: mockOrders,
      total: 1,
      limit: 50,
      offset: 0,
    });

    useAuthStore.setState({
      user: mockAdminUser,
      token: "admin-token",
    });

    render(<HistoricoPedidosPage />);

    await waitFor(() => {
      expect(fetchOrdersSpy).toHaveBeenCalledWith({
        userEmail: "cliente.parceiro@example.com",
        limit: 50,
      });
      expect(screen.getByText("Modo de Consulta Administrativa")).toBeInTheDocument();
      expect(screen.getAllByText("cliente.parceiro@example.com").length).toBeGreaterThan(0);
      expect(screen.getByText("ped-parceiro-200")).toBeInTheDocument();
      expect(screen.getByText("Módulo Fotovoltaico 550W")).toBeInTheDocument();
    });
  });
});

