import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminUsuariosPage from "@/app/admin/usuarios/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as authApi from "@/lib/api/auth";
import * as parceirosApi from "@/lib/api/parceirosB2b";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

describe("AdminUsuariosPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, token: null });
  });

  it("renderiza aviso de acesso restrito se o usuário não for Administrador", () => {
    useAuthStore.setState({
      user: {
        id: 2,
        nome: "João Cliente",
        email: "joao@example.com",
        perfil: "Cliente",
      },
      token: "mock-token",
    });

    render(<AdminUsuariosPage />);

    expect(screen.getByText("Acesso Restrito ao Administrador")).toBeInTheDocument();
  });

  it("carrega e exibe a lista de usuários quando autenticado como Admin", async () => {
    useAuthStore.setState({
      user: {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
      },
      token: "mock-token",
    });

    const mockUsers = [
      {
        id: 1,
        nome: "Admin Teste",
        email: "admin@example.com",
        perfil: "Admin",
        perfil_motivo: "Administrador do Sistema",
      },
      {
        id: 2,
        nome: "Ana Recorrente",
        email: "ana.recorrente@example.com",
        perfil: "Cliente",
        perfil_motivo: "3 compras recentes",
      },
    ];

    const fetchUsersSpy = vi.spyOn(authApi, "fetchUsers").mockResolvedValue(mockUsers);

    render(<AdminUsuariosPage />);

    await waitFor(() => {
      expect(fetchUsersSpy).toHaveBeenCalled();
      expect(
        screen.getByRole("heading", { name: "Gerenciamento de Usuários" }),
      ).toBeInTheDocument();
      expect(screen.getByText("Ana Recorrente")).toBeInTheDocument();
      expect(screen.getByText("ana.recorrente@example.com")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /\+ Novo Usuário \/ Admin/i })).toBeInTheDocument();

      const verPedidosLinks = screen.getAllByRole("link", { name: /Ver Pedidos/i });
      expect(verPedidosLinks[1]).toHaveAttribute(
        "href",
        "/pedidos/historico?email=ana.recorrente%40example.com",
      );
    });
  });

  it("gera a chave B2B de um cliente e mostra o texto uma única vez", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@example.com", perfil: "Admin" },
      token: "mock-token-1",
    });
    vi.spyOn(authApi, "fetchUsers").mockResolvedValue([
      { id: 2, nome: "Revenda", email: "compras@revenda.com", perfil: "Lead", perfil_motivo: "" },
    ]);
    vi.spyOn(parceirosApi, "fetchChavesParceiros").mockResolvedValue([]);
    const gerar = vi.spyOn(parceirosApi, "gerarChaveParceiro").mockResolvedValue({
      cliente_id: 2,
      email: "compras@revenda.com",
      prefixo: "b2b_abcdef",
      chave: "b2b_abcdefSEGREDO",
    });
    const user = userEvent.setup();

    render(<AdminUsuariosPage />);
    await user.click(await screen.findByRole("button", { name: "Gerar chave B2B" }));

    expect(gerar).toHaveBeenCalledWith("mock-token-1", 2);
    expect(await screen.findByLabelText("Chave B2B")).toHaveValue("b2b_abcdefSEGREDO");

    await user.click(screen.getByRole("button", { name: /fechar/i }));
    expect(screen.queryByLabelText("Chave B2B")).not.toBeInTheDocument();
  });

  it("mostra o prefixo da chave ativa e permite revogar", async () => {
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@example.com", perfil: "Admin" },
      token: "mock-token-1",
    });
    vi.spyOn(authApi, "fetchUsers").mockResolvedValue([
      { id: 2, nome: "Revenda", email: "compras@revenda.com", perfil: "Lead", perfil_motivo: "" },
    ]);
    vi.spyOn(parceirosApi, "fetchChavesParceiros").mockResolvedValue([
      {
        cliente_id: 2,
        email: "compras@revenda.com",
        nome: "Revenda",
        prefixo: "b2b_abcdef",
        criada_em: "2026-11-05T10:00:00Z",
      },
    ]);
    const revogar = vi.spyOn(parceirosApi, "revogarChaveParceiro").mockResolvedValue();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const user = userEvent.setup();

    render(<AdminUsuariosPage />);
    expect(await screen.findByText(/b2b_abcdef…/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Revogar" }));

    expect(revogar).toHaveBeenCalledWith("mock-token-1", 2);
  });
});
