import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import AdminDashboardsPage from "@/app/admin/dashboards/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

vi.mock("recharts", async () => {
  const original = await vi.importActual<any>("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => (
      <div data-testid="responsive-container">{children}</div>
    ),
  };
});

const mockCharts = [
  {
    id: "chart-1",
    titulo: "Vendas por Categoria",
    descricao: "Faturamento recente",
    tipo_grafico: "bar",
    config_json: { x_key: "cat", y_keys: ["total"] },
    dados_json: [{ cat: "Ferramentas", total: 1500 }],
    sql_query: "vendas_por_categoria",
    fixado: true,
    ordem: 0,
    criado_em: "2026-10-04T00:00:00Z",
    atualizado_em: "2026-10-04T01:00:00Z",
  },
  {
    id: "chart-2",
    titulo: "Pedidos por Status",
    descricao: "Contagem de pedidos",
    tipo_grafico: "pie",
    config_json: { x_key: "status", y_keys: ["total"] },
    dados_json: [{ status: "Aprovado", total: 10 }],
    sql_query: "pedidos_por_status",
    fixado: false,
    ordem: 1,
    criado_em: "2026-10-04T00:00:00Z",
    atualizado_em: "2026-10-04T01:00:00Z",
  },
];

vi.mock("@/lib/api/charts", () => ({
  fetchAdminCharts: vi.fn().mockImplementation(() => Promise.resolve([...mockCharts])),
  refreshAdminChart: vi
    .fn()
    .mockImplementation((id) =>
      Promise.resolve({ ...mockCharts[0], id, atualizado_em: new Date().toISOString() }),
    ),
  updateAdminChart: vi
    .fn()
    .mockImplementation((id, data) => Promise.resolve({ ...mockCharts[0], id, ...data })),
  deleteAdminChart: vi.fn().mockResolvedValue({ ok: true }),
  createAdminChart: vi.fn().mockImplementation((payload) =>
    Promise.resolve({
      id: "chart-new",
      ...payload,
      criado_em: new Date().toISOString(),
      atualizado_em: new Date().toISOString(),
    }),
  ),
}));

describe("AdminDashboardsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 1, nome: "Administrador", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  it("renderiza o cabeçalho, filtros e lista os gráficos", async () => {
    render(<AdminDashboardsPage />);

    expect(screen.getByText(/Dashboards & Gráficos/i)).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
      expect(screen.getByText("Pedidos por Status")).toBeInTheDocument();
    });
  });

  it("filtra apenas gráficos fixados ao selecionar a aba correspondente", async () => {
    render(<AdminDashboardsPage />);

    await waitFor(() => {
      expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
    });

    const abaFixados = screen.getByRole("button", { name: /Apenas Fixados/i });
    fireEvent.click(abaFixados);

    expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
    expect(screen.queryByText("Pedidos por Status")).not.toBeInTheDocument();
  });

  it("recarrega os gráficos ao receber o evento refresh_admin_charts", async () => {
    const { fetchAdminCharts } = await import("@/lib/api/charts");
    render(<AdminDashboardsPage />);

    await waitFor(() => {
      expect(fetchAdminCharts).toHaveBeenCalledTimes(1);
    });

    fireEvent(window, new CustomEvent("refresh_admin_charts"));

    await waitFor(() => {
      expect(fetchAdminCharts).toHaveBeenCalledTimes(2);
    });
  });

  it("abre modal de criação e adiciona novo gráfico na lista", async () => {
    render(<AdminDashboardsPage />);

    await waitFor(() => {
      expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
    });

    const btnCriar = screen.getByRole("button", { name: /Criar Gráfico/i });
    fireEvent.click(btnCriar);

    expect(screen.getByText("Criar Gráfico Personalizado")).toBeInTheDocument();

    const inputTitulo = screen.getByLabelText(/Título do Gráfico/i);
    fireEvent.change(inputTitulo, { target: { value: "Novo Gráfico Manual" } });

    const catInputs = screen.getAllByPlaceholderText(/Ex: Categoria/i);
    const valInputs = screen.getAllByPlaceholderText(/Ex: 100/i);
    fireEvent.change(catInputs[0], { target: { value: "Cat 1" } });
    fireEvent.change(valInputs[0], { target: { value: "50" } });

    const btnSalvar = screen.getByRole("button", { name: /Salvar Gráfico/i });
    fireEvent.click(btnSalvar);

    await waitFor(() => {
      expect(screen.getByText("Novo Gráfico Manual")).toBeInTheDocument();
    });
  });

  it("não fica preso no esqueleto de carregamento para visitante não-admin", async () => {
    // Achado ao vivo (2026-10-04): sem `hasHydrated` na lista de
    // dependências do efeito de carregamento, um visitante que não é admin
    // (isAdmin/token nunca mudam sozinhos depois do hydrate) nunca via o
    // efeito rodar de novo — a página ficava presa no esqueleto de
    // `animate-pulse` para sempre ("fica rendering").
    useAuthStore.setState({ user: null, token: null });

    render(<AdminDashboardsPage />);

    await waitFor(() => {
      expect(screen.getByText(/Acesso Restrito/i)).toBeInTheDocument();
    });
  });
});
