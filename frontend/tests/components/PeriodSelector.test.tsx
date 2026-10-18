import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PeriodSelector } from "@/components/admin/metricas/PeriodSelector";

const DATA_FIXA = "2026-10-17";

function renderSelector(overrides: Partial<Parameters<typeof PeriodSelector>[0]> = {}) {
  const onPeriodChange = vi.fn();
  const onDateChange = vi.fn();
  render(
    <PeriodSelector
      period="7d"
      selectedDate={DATA_FIXA}
      lastUpdated={null}
      onPeriodChange={onPeriodChange}
      onDateChange={onDateChange}
      {...overrides}
    />,
  );
  return { onPeriodChange, onDateChange };
}

describe("PeriodSelector", () => {
  it("renderiza os quatro botões de período", () => {
    renderSelector();
    expect(screen.getByRole("button", { name: "Hoje" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "7 Dias" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "30 Dias" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tudo" })).toBeInTheDocument();
  });

  it("renderiza o input de data com aria-label acessível", () => {
    renderSelector();
    expect(screen.getByLabelText("Escolher data específica")).toBeInTheDocument();
  });

  it.each([
    ["Hoje", "today"],
    ["7 Dias", "7d"],
    ["30 Dias", "30d"],
    ["Tudo", "all"],
  ] as const)("clique em '%s' chama onPeriodChange('%s')", (label, valor) => {
    const { onPeriodChange } = renderSelector();
    fireEvent.click(screen.getByRole("button", { name: label }));
    expect(onPeriodChange).toHaveBeenCalledOnce();
    expect(onPeriodChange).toHaveBeenCalledWith(valor);
  });

  it("mudar a data chama onDateChange e onPeriodChange('custom')", () => {
    const { onPeriodChange, onDateChange } = renderSelector({ period: "7d" });
    fireEvent.change(screen.getByLabelText("Escolher data específica"), {
      target: { value: "2026-10-10" },
    });
    expect(onDateChange).toHaveBeenCalledWith("2026-10-10");
    expect(onPeriodChange).toHaveBeenCalledWith("custom");
  });

  it("mudar a data quando já está em 'custom' não chama onPeriodChange de novo", () => {
    const { onPeriodChange, onDateChange } = renderSelector({ period: "custom" });
    fireEvent.change(screen.getByLabelText("Escolher data específica"), {
      target: { value: "2026-10-10" },
    });
    expect(onDateChange).toHaveBeenCalledWith("2026-10-10");
    expect(onPeriodChange).not.toHaveBeenCalled();
  });

  it("data vazia não chama nenhum callback", () => {
    const { onPeriodChange, onDateChange } = renderSelector();
    fireEvent.change(screen.getByLabelText("Escolher data específica"), {
      target: { value: "" },
    });
    expect(onDateChange).not.toHaveBeenCalled();
    expect(onPeriodChange).not.toHaveBeenCalled();
  });

  it("exibe 'Calendário' quando o período não é 'custom'", () => {
    renderSelector({ period: "7d" });
    expect(screen.getByText("Calendário")).toBeInTheDocument();
  });

  it("exibe a data formatada no label quando o período é 'custom'", () => {
    renderSelector({ period: "custom", selectedDate: "2026-10-17" });
    // formatarDataPtBr("2026-10-17") => "17/10/2026"
    expect(screen.getByText("17/10/2026")).toBeInTheDocument();
  });

  it("exibe 'Visualizando dia' apenas quando o período é 'custom'", () => {
    const { rerender } = render(
      <PeriodSelector
        period="7d"
        selectedDate={DATA_FIXA}
        lastUpdated={null}
        onPeriodChange={vi.fn()}
        onDateChange={vi.fn()}
      />,
    );
    expect(screen.queryByText(/Visualizando dia/)).not.toBeInTheDocument();

    rerender(
      <PeriodSelector
        period="custom"
        selectedDate={DATA_FIXA}
        lastUpdated={null}
        onPeriodChange={vi.fn()}
        onDateChange={vi.fn()}
      />,
    );
    expect(screen.getByText(/Visualizando dia/)).toBeInTheDocument();
  });

  it("exibe 'Última atualização' quando lastUpdated está preenchido", () => {
    renderSelector({ lastUpdated: new Date("2026-10-17T14:30:00") });
    expect(screen.getByText(/Última atualização/)).toBeInTheDocument();
  });

  it("não exibe 'Última atualização' quando lastUpdated é null", () => {
    renderSelector({ lastUpdated: null });
    expect(screen.queryByText(/Última atualização/)).not.toBeInTheDocument();
  });
});
