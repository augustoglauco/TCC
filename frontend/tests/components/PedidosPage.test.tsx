import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import PedidosPage from "@/app/pedidos/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useCartStore } from "@/lib/hooks/useCartStore";
import * as ordersApi from "@/lib/api/orders";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn() }),
}));

describe("PedidosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
    useCartStore.setState({ items: [] });
  });

  it("renderiza tela de autenticação necessária quando o usuário não estiver logado", async () => {
    render(<PedidosPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Autenticação Necessária" })).toBeInTheDocument();
      expect(
        screen.getByText(/Para entrar em pedidos, acessar seu carrinho e finalizar compras/i),
      ).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /Entrar na Conta/i })).toBeInTheDocument();
    });
  });

  it("renderiza a foto do item do carrinho (regressão: next/image rejeitava hostname dinâmico do backend)", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Ana Recorrente", email: "ana.recorrente@example.com", perfil: "Cliente" },
      token: "mock-token",
    });
    useCartStore.setState({
      items: [
        {
          produtoId: 10,
          nome: "Gerador Solar GD-15",
          preco: 1500.0,
          quantidade: 1,
          centroDistribuicao: "CD-SP",
          imagemUrl: "http://localhost:8000/api/uploads/produtos/foto.jpg",
        },
      ],
    });

    render(<PedidosPage />);

    const img = await screen.findByAltText("Gerador Solar GD-15");
    expect(img).toHaveAttribute("src", "http://localhost:8000/api/uploads/produtos/foto.jpg");
  });

  it("renderiza o carrinho e permite finalizar pedido quando autenticado", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    useCartStore.setState({
      items: [
        {
          produtoId: 10,
          nome: "Gerador Solar GD-15",
          preco: 1500.0,
          quantidade: 1,
          centroDistribuicao: "CD-SP",
        },
      ],
    });

    const createOrderSpy = vi.spyOn(ordersApi, "createOrder").mockResolvedValue({
      id: "ord-test-999",
      status: "reservado",
      criado_em: "2026-09-29T10:00:00Z",
      user_email: "ana.recorrente@example.com",
      valor_total: 1500.0,
      itens: [],
    });

    render(<PedidosPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Pedidos, Frete & Preços Diferenciados B2B" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Ana Recorrente")).toBeInTheDocument();
      expect(screen.getByText("ana.recorrente@example.com")).toBeInTheDocument();
    });

    const finishBtn = screen.getByRole("button", { name: /Finalizar Pedido & Reservar/i });
    fireEvent.click(finishBtn);

    await waitFor(() => {
      expect(createOrderSpy).toHaveBeenCalledWith({
        user_email: "ana.recorrente@example.com",
        conversation_id: undefined,
        itens: [
          {
            produto_id: 10,
            quantidade: 1,
            centro_distribuicao: "CD-SP",
          },
        ],
      });
      expect(screen.getByText("Pedido Reservado com Sucesso!")).toBeInTheDocument();
      expect(screen.getByText("ID do Pedido: ord-test-999")).toBeInTheDocument();
    });
  });
});
