import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import CadastroPage from "@/app/conta/cadastro/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe("CadastroPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza os campos do formulário de novo cadastro", () => {
    render(<CadastroPage />);

    expect(screen.getByRole("heading", { name: "Novo Cadastro de Usuário" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Nome Completo/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Endereço de E-mail/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Senha de Acesso/i)).toBeInTheDocument();
    expect(screen.getByText("👤 Simples (Cliente)")).toBeInTheDocument();
    expect(screen.getByText("⚙️ Administrador")).toBeInTheDocument();
  });

  it("realiza cadastro de usuário simples e redireciona para perfil", async () => {
    const mockRegister = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({ register: mockRegister });

    render(<CadastroPage />);

    fireEvent.change(screen.getByLabelText(/Nome Completo/i), {
      target: { value: "Lucas Silva" },
    });
    fireEvent.change(screen.getByLabelText(/Endereço de E-mail/i), {
      target: { value: "lucas@example.com" },
    });

    const submitBtn = screen.getByRole("button", { name: /Criar Minha Conta/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        nome: "Lucas Silva",
        email: "lucas@example.com",
        password: "12345",
        perfil: "Cliente",
      });
      expect(mockPush).toHaveBeenCalledWith("/conta/perfil");
    });
  });

  it("realiza cadastro de usuário Admin e redireciona para painel admin quando autenticado como Admin", async () => {
    const mockRegister = vi.fn().mockResolvedValue(undefined);
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Principal",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
      register: mockRegister,
    });

    render(<CadastroPage />);

    fireEvent.change(screen.getByLabelText(/Nome Completo/i), {
      target: { value: "Mariana Admin" },
    });
    fireEvent.change(screen.getByLabelText(/Endereço de E-mail/i), {
      target: { value: "admin.mariana@example.com" },
    });

    // Seleciona botão de Administrador
    const adminRoleBtn = screen.getByText("⚙️ Administrador").closest("button");
    if (adminRoleBtn) fireEvent.click(adminRoleBtn);

    const submitBtn = screen.getByRole("button", { name: /Criar Minha Conta/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        nome: "Mariana Admin",
        email: "admin.mariana@example.com",
        password: "12345",
        perfil: "Admin",
        requesterEmail: "admin@example.com",
      });
      expect(mockPush).toHaveBeenCalledWith("/admin/produtos");
    });
  });
});
