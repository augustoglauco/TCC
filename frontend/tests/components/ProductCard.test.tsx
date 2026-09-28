import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProductCard } from "@/components/products/ProductCard";
import { Produto } from "@/lib/api/products";

// Mock do useRouter do Next.js
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

const MOCK_PRODUCT: Produto = {
  id: 1,
  nome: "Câmera Bullet IP 4MP",
  descricao: "Câmera de segurança para áreas externas",
  preco: 450.0,
  categoria: "CFTV",
  imagem_url: "/api/uploads/produtos/foto1.jpg",
  imagens: [
    { id: 10, imagem_url: "/api/uploads/produtos/foto1.jpg", is_principal: true, criado_em: "2026-09-27" },
    { id: 11, imagem_url: "/api/uploads/produtos/foto2.jpg", is_principal: false, criado_em: "2026-09-27" },
  ],
  estoques: [{ id: "est-1", centro_distribuicao: "CD-Matriz", quantidade: 15, atualizado_em: "2026-09-27" }],
};

describe("ProductCard", () => {
  it("renderiza nome, categoria, preço e status de estoque", () => {
    const handleZoom = vi.fn();
    render(<ProductCard product={MOCK_PRODUCT} onOpenZoom={handleZoom} />);

    expect(screen.getByText("Câmera Bullet IP 4MP")).toBeInTheDocument();
    expect(screen.getByText("CFTV")).toBeInTheDocument();
    expect(screen.getByText("R$ 450,00")).toBeInTheDocument();
    expect(screen.getByText("Em estoque (15 un)")).toBeInTheDocument();
  });

  it("permite alternar fotos pelas setas de navegação", () => {
    const handleZoom = vi.fn();
    render(<ProductCard product={MOCK_PRODUCT} onOpenZoom={handleZoom} />);

    // Indicador de foto (1 / 2)
    expect(screen.getByText("1 / 2")).toBeInTheDocument();

    // Clica na seta da direita (Próxima imagem)
    const nextButton = screen.getByLabelText("Próxima imagem");
    fireEvent.click(nextButton);

    expect(screen.getByText("2 / 2")).toBeInTheDocument();
  });

  it("chama onOpenZoom ao clicar na imagem ou no botão de zoom", () => {
    const handleZoom = vi.fn();
    render(<ProductCard product={MOCK_PRODUCT} onOpenZoom={handleZoom} />);

    const img = screen.getByAltText("Câmera Bullet IP 4MP");
    fireEvent.click(img);

    expect(handleZoom).toHaveBeenCalledWith("http://localhost:8000/api/uploads/produtos/foto1.jpg");
  });
});
