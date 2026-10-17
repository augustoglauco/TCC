import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HardwareReveal from "@/components/home/HardwareReveal";

describe("HardwareReveal", () => {
  it("renderiza a lista de 5 equipamentos e atualiza o display ao selecionar", () => {
    render(<HardwareReveal />);
    expect(screen.getByText("01")).toBeInTheDocument();
    expect(screen.getAllByText(/iDFace/i)[0]).toBeInTheDocument();

    // Troca para o item 02 (iDBlock)
    const item2 = screen.getByText(/Catraca de Pedestal em Inox iDBlock/i);
    fireEvent.mouseEnter(item2);
    expect(screen.getAllByText(/Catraca de Pedestal em Inox iDBlock/i).length).toBeGreaterThan(1);
  });

  it("permite selecionar equipamento por clique para suporte a dispositivos touch", () => {
    render(<HardwareReveal />);
    const item3 = screen.getByText(/Relógio de Ponto Eletrônico REP iDClass/i);
    fireEvent.click(item3);
    expect(screen.getAllByText(/Portaria 671/i).length).toBeGreaterThan(0);
  });
});
