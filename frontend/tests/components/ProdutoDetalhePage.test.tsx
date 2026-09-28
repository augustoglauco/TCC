import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ProdutoDetalhePage from "@/app/produtos/[id]/page";
import * as productsApi from "@/lib/api/products";
import { useChatStore } from "@/lib/hooks/useChatStore";

// Mock do useRouter do Next.js
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

const MOCK_PRODUTO_COMPLETO: productsApi.Produto = {
  id: 42,
  nome: "Câmera Bullet IP 4K Ultra",
  descricao: "Câmera de segurança externa com inteligência artificial",
  preco: 850.0,
  preco_promocional: 750.0,
  categoria: "CFTV",
  especificacoes_tecnicas: "Resolução 4K Ultra HD\nSensor CMOS 1/2.8\nAlcance IR 30m",
  dimensoes_cm: "18 x 7 x 7",
  peso_kg: 0.65,
  imagem_url: "/api/uploads/produtos/camera-principal.jpg",
  imagens: [
    {
      id: 1,
      imagem_url: "/api/uploads/produtos/camera-principal.jpg",
      is_principal: true,
      criado_em: "2026-09-28",
    },
    {
      id: 2,
      imagem_url: "/api/uploads/produtos/camera-secundaria.jpg",
      is_principal: false,
      criado_em: "2026-09-28",
    },
  ],
  estoques: [
    {
      id: "est-1",
      centro_distribuicao: "CD São Paulo",
      quantidade: 10,
      atualizado_em: "2026-09-28",
    },
    {
      id: "est-2",
      centro_distribuicao: "CD Curitiba",
      quantidade: 5,
      atualizado_em: "2026-09-28",
    },
  ],
  descontos_volume: [
    {
      id: "desc-1",
      quantidade_minima: 5,
      percentual_desconto: 10,
    },
  ],
};

describe("ProdutoDetalhePage", () => {
  it("renderiza todos os detalhes do produto carregado", async () => {
    vi.spyOn(productsApi, "fetchProductById").mockResolvedValue(MOCK_PRODUTO_COMPLETO);

    render(<ProdutoDetalhePage params={{ id: "42" }} />);

    expect(
      await screen.findByRole("heading", { name: "Câmera Bullet IP 4K Ultra", level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("CFTV").length).toBeGreaterThan(0);
    expect(screen.getByText("R$ 750,00")).toBeInTheDocument();
    expect(screen.getByText("R$ 850,00")).toBeInTheDocument();
    expect(screen.getByText("Em estoque (15 un)")).toBeInTheDocument();
    expect(screen.getByText("CD São Paulo")).toBeInTheDocument();
    expect(screen.getByText("CD Curitiba")).toBeInTheDocument();
    expect(screen.getByText("18 x 7 x 7 cm")).toBeInTheDocument();
    expect(screen.getByText("0.65 kg")).toBeInTheDocument();
    expect(screen.getByText(/Resolução 4K Ultra HD/)).toBeInTheDocument();
    expect(screen.getByText(/A partir de 5 un:/)).toBeInTheDocument();
  });

  it("permite navegar no fluxo de compra e cotar pelo chat", async () => {
    vi.spyOn(productsApi, "fetchProductById").mockResolvedValue(MOCK_PRODUTO_COMPLETO);
    const chatOpenSpy = vi.spyOn(useChatStore.getState(), "open");

    render(<ProdutoDetalhePage params={{ id: "42" }} />);

    const buyButton = await screen.findByRole("button", { name: /Comprar Agora/i });
    fireEvent.click(buyButton);
    expect(mockPush).toHaveBeenCalledWith("/pedidos?produto=42");

    const quoteButton = screen.getByRole("button", { name: /Cotar com Assistente/i });
    fireEvent.click(quoteButton);
    expect(chatOpenSpy).toHaveBeenCalled();
  });

  it("renderiza tela amigável quando produto não é encontrado", async () => {
    vi.spyOn(productsApi, "fetchProductById").mockRejectedValue(
      new Error("Produto não encontrado."),
    );

    render(<ProdutoDetalhePage params={{ id: "999" }} />);

    expect(await screen.findByText("Produto não encontrado")).toBeInTheDocument();
    expect(screen.getByText("← Voltar ao Catálogo")).toBeInTheDocument();
  });
});
