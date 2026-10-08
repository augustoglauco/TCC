import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ChatChartCard from "@/components/chat/cards/ChatChartCard";
import ChatCard from "@/components/chat/cards/ChatCard";
import DynamicChartCard from "@/components/admin/DynamicChartCard";
import type { ChatCardGrafico } from "@/lib/types/chat";

vi.mock("next/link", () => ({
  default: ({ children, href, onClick, ...rest }: any) => (
    <a
      href={href}
      onClick={(e) => {
        e.preventDefault();
        onClick?.(e);
      }}
      {...rest}
    >
      {children}
    </a>
  ),
}));

vi.mock("recharts", async () => {
  const original = await vi.importActual<any>("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  };
});

describe("ChatChartCard", () => {
  const mockCard: ChatCardGrafico = {
    tipo: "grafico",
    chart_id: "test-uuid-1",
    titulo: "Vendas por Categoria",
    tipo_grafico: "bar",
    config: { x_key: "cat", y_keys: ["val"] },
    dados: [{ cat: "Ferramentas", val: 150 }],
    fixado: true,
  };

  it("renderiza título, indicador de tipo e link para o painel", () => {
    render(<ChatChartCard card={mockCard} />);

    expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Ver no painel de dashboards/i }),
    ).toHaveAttribute("href", "/admin/dashboards");
  });

  it("renderiza via despachante ChatCard", () => {
    render(<ChatCard card={mockCard} />);
    expect(screen.getByText("Vendas por Categoria")).toBeInTheDocument();
  });

  it("fecha o modal do chat e dispara evento de refresh ao clicar no link", () => {
    const dispatchSpy = vi.spyOn(window, "dispatchEvent");
    render(<ChatChartCard card={mockCard} />);

    const link = screen.getByRole("link", { name: /Ver no painel de dashboards/i });
    fireEvent.click(link);

    expect(dispatchSpy).toHaveBeenCalledWith(
      expect.objectContaining({ type: "refresh_admin_charts" }),
    );
    dispatchSpy.mockRestore();
  });
});

describe("DynamicChartCard", () => {
  const mockChart = {
    id: "chart-123",
    titulo: "Estoque por CD",
    descricao: "Distribuição física",
    tipo_grafico: "pie",
    config_json: { x_key: "cd", y_keys: ["qtd"] },
    dados_json: [{ cd: "SP", qtd: 50 }],
    fixado: true,
    ordem: 0,
    criado_em: "2026-10-04T00:00:00Z",
    atualizado_em: "2026-10-04T01:00:00Z",
  };

  it("renderiza título, ações e aciona callbacks", async () => {
    const onRefresh = vi.fn().mockResolvedValue(undefined);
    const onTogglePin = vi.fn().mockResolvedValue(undefined);
    const onDelete = vi.fn().mockResolvedValue(undefined);

    render(
      <DynamicChartCard
        chart={mockChart}
        onRefresh={onRefresh}
        onTogglePin={onTogglePin}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText("Estoque por CD")).toBeInTheDocument();
    expect(screen.getByText("Distribuição física")).toBeInTheDocument();

    const refreshBtn = screen.getByTitle(/Atualizar dados/i);
    fireEvent.click(refreshBtn);
    expect(onRefresh).toHaveBeenCalledWith("chart-123");

    const pinBtn = screen.getByTitle(/Desafixar/i);
    fireEvent.click(pinBtn);
    expect(onTogglePin).toHaveBeenCalledWith("chart-123", false);

    const deleteBtn = screen.getByTitle(/Excluir gráfico/i);
    fireEvent.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledWith("chart-123");
  });

  it("exibe engrenagem e abre o bubble com a consulta SQL dinâmico ao clicar", () => {
    const chartComSql = {
      ...mockChart,
      sql_query: "dynamic_sql: SELECT * FROM produtos",
    };

    render(
      <DynamicChartCard
        chart={chartComSql}
        onRefresh={vi.fn()}
        onTogglePin={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    // O SQL não deve estar visível no DOM antes de clicar na engrenagem
    expect(screen.queryByText("dynamic_sql: SELECT * FROM produtos")).not.toBeInTheDocument();

    // Clica no botão de SQL Dinâmico com ícone de engrenagem
    const gearBtn = screen.getByTitle("Exibir SQL Dinâmico");
    expect(gearBtn).toBeInTheDocument();
    fireEvent.click(gearBtn);

    // Agora o bubble deve exibir o SQL
    expect(screen.getByText("dynamic_sql: SELECT * FROM produtos")).toBeInTheDocument();

    // Clica novamente para fechar
    fireEvent.click(gearBtn);
    expect(screen.queryByText("dynamic_sql: SELECT * FROM produtos")).not.toBeInTheDocument();
  });
});

