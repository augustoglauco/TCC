import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CapabilitiesGrid from "@/components/home/CapabilitiesGrid";

describe("CapabilitiesGrid", () => {
  it("renderiza os 4 domínios de atendimento e soluções", () => {
    render(<CapabilitiesGrid />);
    expect(screen.getByText(/Controle de Acesso/i)).toBeInTheDocument();
    expect(screen.getByText(/Bloqueios & Catracas/i)).toBeInTheDocument();
    expect(screen.getByText(/Ponto Eletrônico/i)).toBeInTheDocument();
    expect(screen.getByText(/Automação & Protocolo MCP/i)).toBeInTheDocument();
  });
});
