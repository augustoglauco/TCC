import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ProductCard from "@/components/chat/cards/ProductCard";
import type { ChatCardProduto } from "@/lib/types/chat";

function makeCard(overrides: Partial<ChatCardProduto> = {}): ChatCardProduto {
  return {
    tipo: "produto",
    produto_id: 1,
    nome: "Gerador Diesel GD-15",
    preco: "24900.00",
    imagem_url: null,
    estoque_total: 8,
    ...overrides,
  };
}

describe("ProductCard (chat)", () => {
  it("renderiza nome, preço formatado e estoque disponível", () => {
    render(<ProductCard card={makeCard()} />);

    expect(screen.getByText("Gerador Diesel GD-15")).toBeInTheDocument();
    expect(screen.getByText("R$ 24.900,00")).toBeInTheDocument();
    expect(screen.getByText("8 em estoque")).toBeInTheDocument();
  });

  it("mostra 'Sem estoque' quando estoque_total é 0", () => {
    render(<ProductCard card={makeCard({ estoque_total: 0 })} />);

    expect(screen.getByText("Sem estoque")).toBeInTheDocument();
  });

  it("linka para a página de detalhe do produto", () => {
    render(<ProductCard card={makeCard({ produto_id: 42 })} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", "/produtos/42");
  });

  it("mostra um ícone padrão quando não há imagem", () => {
    render(<ProductCard card={makeCard({ imagem_url: null })} />);

    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("📦")).toBeInTheDocument();
  });

  it("renderiza a imagem quando imagem_url está presente", () => {
    render(<ProductCard card={makeCard({ imagem_url: "/api/uploads/produtos/gd15.jpg" })} />);

    const img = screen.getByRole("img", { name: "Gerador Diesel GD-15" });
    expect(img).toHaveAttribute("src", expect.stringContaining("/api/uploads/produtos/gd15.jpg"));
  });
});
