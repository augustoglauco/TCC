import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProdutosPage from "@/app/produtos/page";
import * as productsApi from "@/lib/api/products";
import type { Produto } from "@/lib/api/products";

vi.mock("@/lib/api/products", () => ({
  fetchProducts: vi.fn(),
  fetchProductCategories: vi.fn(),
}));

vi.mock("@/components/products/ProductCard", () => ({
  ProductCard: ({ product }: { product: Produto; onOpenZoom: (url: string) => void }) => (
    <div data-testid={`product-card-${product.id}`}>{product.nome}</div>
  ),
}));

vi.mock("@/components/products/ImageZoomModal", () => ({
  ImageZoomModal: ({ productName, onClose }: { imageUrl: string; productName: string; onClose: () => void }) => (
    <div data-testid="zoom-modal">
      <span>{productName}</span>
      <button type="button" onClick={onClose}>Fechar zoom</button>
    </div>
  ),
}));

const makeProduto = (overrides: Partial<Produto> = {}): Produto => ({
  id: 1,
  nome: "Produto Teste",
  descricao: "Desc",
  categoria: "Controle de Acesso",
  preco: 1000,
  imagens: [],
  estoques: [],
  descontos_volume: [],
  ...overrides,
});

const defaultPaginatedResponse = (items: Produto[] = [makeProduto()]) => ({
  items,
  total: items.length,
  limit: 12,
  offset: 0,
});

describe("ProdutosPage — catálogo público", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(productsApi.fetchProductCategories).mockResolvedValue(["Controle de Acesso", "Ponto"]);
    vi.mocked(productsApi.fetchProducts).mockResolvedValue(defaultPaginatedResponse());
  });

  it("exibe spinner durante carregamento e depois renderiza produto", async () => {
    render(<ProdutosPage />);
    expect(screen.getByText(/Carregando catálogo/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("product-card-1")).toBeInTheDocument());
  });

  it("exibe mensagem de erro quando fetchProducts rejeita", async () => {
    vi.mocked(productsApi.fetchProducts).mockRejectedValue(new Error("Falha de rede"));
    render(<ProdutosPage />);
    await waitFor(() =>
      expect(screen.getByText(/Não foi possível carregar o catálogo/i)).toBeInTheDocument(),
    );
  });

  it("exibe estado vazio quando não há produtos", async () => {
    vi.mocked(productsApi.fetchProducts).mockResolvedValue(defaultPaginatedResponse([]));
    render(<ProdutosPage />);
    await waitFor(() =>
      expect(screen.getByText(/Nenhum produto encontrado/i)).toBeInTheDocument(),
    );
  });

  it("renderiza categorias carregadas como filtros", async () => {
    render(<ProdutosPage />);
    // Aguarda os botões de filtro aparecerem (role=button dentro do header)
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Controle de Acesso" }).length).toBeGreaterThan(0),
    );
    expect(screen.getByRole("button", { name: "Ponto" })).toBeInTheDocument();
    expect(screen.getByText(/Todas as categorias/i)).toBeInTheDocument();
  });

  it("filtra por categoria ao clicar na pílula", async () => {
    const user = userEvent.setup();
    render(<ProdutosPage />);
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Controle de Acesso" }).length).toBeGreaterThan(0),
    );

    const callsBefore = vi.mocked(productsApi.fetchProducts).mock.calls.length;
    // Clica no primeiro botão de filtro com esse nome
    await user.click(screen.getAllByRole("button", { name: "Controle de Acesso" })[0]);
    await waitFor(() =>
      expect(vi.mocked(productsApi.fetchProducts).mock.calls.length).toBeGreaterThan(callsBefore),
    );
    const lastCall = vi.mocked(productsApi.fetchProducts).mock.calls.at(-1)?.[0];
    expect(lastCall?.categoria).toBe("Controle de Acesso");
  });

  it("abre e fecha modal de zoom ao clicar em miniatura do banner", async () => {
    const user = userEvent.setup();
    render(<ProdutosPage />);
    await waitFor(() => expect(screen.getByTestId("product-card-1")).toBeInTheDocument());

    // Clica na primeira miniatura do banner (visível em sm+)
    const thumbButtons = screen.getAllByTitle(/Ampliar/i);
    await user.click(thumbButtons[0]);
    expect(screen.getByTestId("zoom-modal")).toBeInTheDocument();

    await user.click(screen.getByText("Fechar zoom"));
    expect(screen.queryByTestId("zoom-modal")).not.toBeInTheDocument();
  });

  it("exibe paginação quando há mais de 12 produtos", async () => {
    vi.mocked(productsApi.fetchProducts).mockResolvedValue({
      items: [makeProduto()],
      total: 25,
      limit: 12,
      offset: 0,
    });
    render(<ProdutosPage />);
    await waitFor(() => expect(screen.getByText("Próximo")).toBeInTheDocument());
    expect(screen.getByText("Anterior")).toBeInTheDocument();
  });

  it("exibe botão Próximo desabilitado quando há apenas 1 produto (1 página)", async () => {
    render(<ProdutosPage />);
    await waitFor(() => expect(screen.getByTestId("product-card-1")).toBeInTheDocument());
    // Paginação sempre renderiza, mas o botão Próximo fica disabled na última página
    expect(screen.getByText("Próximo")).toBeDisabled();
  });

  it("agrupa produtos por categoria na listagem", async () => {
    vi.mocked(productsApi.fetchProducts).mockResolvedValue(
      defaultPaginatedResponse([
        makeProduto({ id: 1, nome: "Prod A", categoria: "Controle de Acesso" }),
        makeProduto({ id: 2, nome: "Prod B", categoria: "Ponto" }),
      ]),
    );
    render(<ProdutosPage />);
    await waitFor(() => expect(screen.getByTestId("product-card-1")).toBeInTheDocument());
    expect(screen.getByTestId("product-card-2")).toBeInTheDocument();
  });
});
