import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import CadastroPage from "@/app/conta/cadastro/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as authApi from "@/lib/api/auth";
import * as parceirosApi from "@/lib/api/parceirosB2b";

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

  it("admin cadastra um parceiro B2B, recebe a chave e a sessão dele não muda", async () => {
    const mockRegister = vi.fn();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@example.com", perfil: "Admin" },
      token: "mock-token-1",
      register: mockRegister,
    });
    const registrar = vi.spyOn(authApi, "register").mockResolvedValue({
      token: "mock-token-7",
      user: { id: 7, nome: "Revenda", email: "compras@revenda.com", perfil: "Cliente" },
    });
    const gerar = vi.spyOn(parceirosApi, "gerarChaveParceiro").mockResolvedValue({
      cliente_id: 7,
      email: "compras@revenda.com",
      prefixo: "b2b_abcdef",
      chave: "b2b_abcdefSEGREDO",
    });

    render(<CadastroPage />);
    fireEvent.change(screen.getByLabelText(/Nome Completo/i), { target: { value: "Revenda" } });
    fireEvent.change(screen.getByLabelText(/Endereço de E-mail/i), {
      target: { value: "compras@revenda.com" },
    });
    fireEvent.click(screen.getByText("🏢 Parceiro B2B"));
    fireEvent.click(screen.getByRole("button", { name: /Cadastrar Parceiro e Gerar Chave/i }));

    await waitFor(() => {
      expect(registrar).toHaveBeenCalledWith(
        expect.objectContaining({ email: "compras@revenda.com", perfil: "Cliente" }),
      );
      expect(gerar).toHaveBeenCalledWith("mock-token-1", 7);
    });
    expect(await screen.findByLabelText("Chave B2B")).toHaveValue("b2b_abcdefSEGREDO");
    expect(mockRegister).not.toHaveBeenCalled();
  });

  it("a opção Parceiro B2B só aparece para administrador", () => {
    render(<CadastroPage />);
    expect(screen.queryByText("🏢 Parceiro B2B")).not.toBeInTheDocument();
  });
});
