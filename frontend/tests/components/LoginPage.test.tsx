import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import LoginPage from "@/app/conta/login/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza o formulário de login e contas de demonstração", () => {
    render(<LoginPage />);

    expect(screen.getByRole("heading", { name: "Entrar na Conta" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Endereço de E-mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Senha de Acesso/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Entrar$/i })).toBeInTheDocument();

    // Contas demo
    expect(screen.getByText("Ana Recorrente")).toBeInTheDocument();
    expect(screen.getByText("Bruno Único")).toBeInTheDocument();
    expect(screen.getByText("Carla Antiga")).toBeInTheDocument();
  });

  it("realiza login ao submeter o formulário com sucesso", async () => {
    const mockLogin = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ login: mockLogin });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/Endereço de E-mail/i);
    fireEvent.change(emailInput, { target: { value: "teste@example.com" } });

    const submitBtn = screen.getByRole("button", { name: /^Entrar$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("teste@example.com", "12345");
      expect(mockPush).toHaveBeenCalledWith("/conta/perfil");
    });
  });

  it("realiza login rápido com conta de demonstração", async () => {
    const mockLogin = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ login: mockLogin });

    render(<LoginPage />);

    const anaBtn = screen.getByRole("button", { name: /Ana Recorrente/i });
    fireEvent.click(anaBtn);

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("ana.recorrente@example.com", "12345");
      expect(mockPush).toHaveBeenCalledWith("/conta/perfil");
    });
  });

  it("exibe mensagem de erro quando o login falha", async () => {
    const mockLogin = vi.fn().mockRejectedValue(new Error("Senha incorreta"));
    useAuthStore.setState({ login: mockLogin });

    render(<LoginPage />);

    const emailInput = screen.getByLabelText(/Endereço de E-mail/i);
    fireEvent.change(emailInput, { target: { value: "errado@example.com" } });

    const submitBtn = screen.getByRole("button", { name: /^Entrar$/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(screen.getByText("Senha incorreta")).toBeInTheDocument();
    });
  });

  it("exibe tela de sessão ativa quando o usuário já está autenticado", () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    render(<LoginPage />);

    expect(screen.getByText("Sessão Ativa")).toBeInTheDocument();
    expect(screen.getByText(/Você está autenticado como/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver Meu Perfil e Pedidos/i })).toBeInTheDocument();
  });
});
