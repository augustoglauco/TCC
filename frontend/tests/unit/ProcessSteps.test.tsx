import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ProcessSteps from "@/components/home/ProcessSteps";

describe("ProcessSteps", () => {
  it("renderiza os 4 passos numerados do fluxo de atendimento inteligente", () => {
    render(<ProcessSteps />);
    expect(screen.getByText(/Como Trabalhamos/i)).toBeInTheDocument();
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getByText(/Consulta Multimodal/i)).toBeInTheDocument();
    expect(screen.getByText("02")).toBeInTheDocument();
    expect(screen.getByText(/Roteamento Híbrido/i)).toBeInTheDocument();
    expect(screen.getByText("03")).toBeInTheDocument();
    expect(screen.getByText(/Cotação MCP B2B/i)).toBeInTheDocument();
    expect(screen.getByText("04")).toBeInTheDocument();
    expect(screen.getByText(/Agendamento de Visita/i)).toBeInTheDocument();
  });
});
