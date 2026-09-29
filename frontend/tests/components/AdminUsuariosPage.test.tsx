import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminUsuariosPage from "@/app/admin/usuarios/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import * as authApi from "@/lib/api/auth";

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
      expect(screen.getByRole("heading", { name: "Gerenciamento de Usuários" })).toBeInTheDocument();
      expect(screen.getByText("Ana Recorrente")).toBeInTheDocument();
      expect(screen.getByText("ana.recorrente@example.com")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: /\+ Novo Usuário \/ Admin/i })).toBeInTheDocument();
    });
  });
});
