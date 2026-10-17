import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Header from "@/components/layout/Header";
import Footer from "@/components/layout/Footer";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
}));

describe("Header e Footer", () => {
  it("renderiza o Header com a marca Empresa Fictícia e botão de Chat", () => {
    render(<Header />);
    expect(screen.getAllByText(/Empresa Fictícia/i)[0]).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /falar com assistente ia/i })).toBeInTheDocument();
  });

  it("renderiza o Footer com colunas de navegação e selo do TCC", () => {
    render(<Footer />);
    expect(screen.getByText(/Protótipo TCC/i)).toBeInTheDocument();
    expect(screen.getByText(/Controle de Acesso/i)).toBeInTheDocument();
  });
});
