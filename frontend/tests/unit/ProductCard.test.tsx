import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductCard } from "@/components/products/ProductCard";
import { Produto } from "@/lib/api/products";

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const mockProdutoSemFoto: Produto = {
  id: 1,
  nome: "Terminal Facial iDFace",
  descricao: "Leitor facial com tela touch",
  especificacoes_tecnicas: "Leitura 0.2s • IP65 • SIP integrado",
  categoria: "Controle de Acesso",
  preco: 2490,
  imagem_url: null,
  imagens: [],
  estoques: [
    { id: "est-1", quantidade: 10, centro_distribuicao: "CD-SP", atualizado_em: "2026-10-17" },
  ],
};

describe("ProductCard (Galeria Técnica M3 Glass)", () => {
  it("renderiza especificacoes resumidas, botoes Comprar/Cotar e preserva Sem foto cadastrada quando imagem_url e null", () => {
    render(<ProductCard product={mockProdutoSemFoto} onOpenZoom={vi.fn()} />);
    expect(screen.getByText("Terminal Facial iDFace")).toBeInTheDocument();
    expect(screen.getByText("Sem foto cadastrada")).toBeInTheDocument();
    expect(screen.getByText(/Leitura 0.2s • IP65/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /comprar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cotar/i })).toBeInTheDocument();
  });
});
