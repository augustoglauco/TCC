import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ChartRenderer from "@/components/charts/ChartRenderer";

vi.mock("recharts", async () => {
  const original = await vi.importActual<any>("recharts");
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => <div data-testid="responsive-container">{children}</div>,
  };
});

describe("ChartRenderer", () => {
  it("renderiza estado vazio quando dados é lista vazia", () => {
    render(<ChartRenderer tipo_grafico="bar" config={{}} dados={[]} />);
    expect(screen.getByText(/Nenhum dado disponível/i)).toBeInTheDocument();
  });

  it("renderiza gráfico de barras quando tipo_grafico é 'bar'", () => {
    const dados = [
      { categoria: "Ferramentas", total: 1500 },
      { categoria: "Elétrica", total: 3200 },
    ];
    const config = {
      x_key: "categoria",
      y_keys: ["total"],
      labels: { total: "Total (R$)" },
    };
    render(<ChartRenderer tipo_grafico="bar" config={config} dados={dados} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renderiza gráfico de linhas quando tipo_grafico é 'line'", () => {
    const dados = [
      { data: "2026-10-01", total: 10 },
      { data: "2026-10-02", total: 25 },
    ];
    const config = {
      x_key: "data",
      y_keys: ["total"],
    };
    render(<ChartRenderer tipo_grafico="line" config={config} dados={dados} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });

  it("renderiza gráfico de pizza quando tipo_grafico é 'pie'", () => {
    const dados = [
      { status: "Aprovado", total: 40 },
      { status: "Pendente", total: 10 },
    ];
    const config = {
      x_key: "status",
      y_keys: ["total"],
    };
    render(<ChartRenderer tipo_grafico="pie" config={config} dados={dados} />);
    expect(screen.getByTestId("responsive-container")).toBeInTheDocument();
  });
});
