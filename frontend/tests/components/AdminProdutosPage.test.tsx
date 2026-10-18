import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminProdutosPage from "@/app/admin/produtos/page";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { AdminProduct } from "@/lib/types/adminProducts";

vi.mock("@/lib/api/adminProducts", () => ({
  fetchAdminProducts: vi.fn(),
  fetchAdminCategories: vi.fn(),
  deleteAdminProduct: vi.fn(),
}));

vi.mock("@/components/admin/products/ProductListTable", () => ({
  default: ({
    produtos,
    loading,
    onEdit,
    onDelete,
  }: {
    produtos: AdminProduct[];
    loading: boolean;
    onEdit: (p: AdminProduct) => void;
    onDelete: (id: number) => void;
  }) => (
    <div data-testid="product-list-table">
      {loading && <span>Carregando...</span>}
      {produtos.map((p) => (
        <div key={p.id} data-testid={`produto-${p.id}`}>
          <span>{p.nome}</span>
          <button type="button" onClick={() => onEdit(p)}>
            Editar {p.nome}
          </button>
          <button type="button" onClick={() => onDelete(p.id)}>
            Excluir {p.nome}
          </button>
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/admin/products/ProductFormModal", () => ({
  default: ({
    isOpen,
    onClose,
    produtoParaEditar,
  }: {
    isOpen: boolean;
    onClose: () => void;
    produtoParaEditar: AdminProduct | null;
    onSuccess: () => void;
    allProducts: AdminProduct[];
  }) =>
    isOpen ? (
      <div data-testid="product-form-modal">
        <span>{produtoParaEditar ? `Editando: ${produtoParaEditar.nome}` : "Novo produto"}</span>
        <button type="button" onClick={onClose}>
          Fechar modal
        </button>
      </div>
    ) : null,
}));

vi.mock("@/components/admin/products/CatalogImportModal", () => ({
  default: ({
    isOpen,
    onClose,
  }: {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
  }) =>
    isOpen ? (
      <div data-testid="catalog-import-modal">
        <button type="button" onClick={onClose}>
          Fechar importação
        </button>
      </div>
    ) : null,
}));

vi.mock("@/components/admin/products/CategoryFilter", () => ({
  default: ({
    selectedCategories,
    onChange,
    availableCategories,
  }: {
    selectedCategories: string[];
    onChange: (cats: string[]) => void;
    availableCategories: string[];
    categoryCounts: Record<string, number>;
  }) => (
    <div data-testid="category-filter">
      {availableCategories.map((cat) => (
        <button
          key={cat}
          type="button"
          onClick={() =>
            onChange(
              selectedCategories.includes(cat)
                ? selectedCategories.filter((c) => c !== cat)
                : [...selectedCategories, cat],
            )
          }
        >
          {cat}
        </button>
      ))}
    </div>
  ),
}));

import {
  deleteAdminProduct,
  fetchAdminCategories,
  fetchAdminProducts,
} from "@/lib/api/adminProducts";

const mockedFetchProducts = vi.mocked(fetchAdminProducts);
const mockedFetchCategories = vi.mocked(fetchAdminCategories);
const mockedDeleteProduct = vi.mocked(deleteAdminProduct);

const PRODUTO_1: AdminProduct = {
  id: 1,
  nome: "Câmera IP HD",
  descricao: "Câmera de segurança",
  preco: 450,
  categoria: "CFTV",
  preco_base_fornecedor: 300,
  imagem_url: null,
  imagens: [],
};

const PRODUTO_2: AdminProduct = {
  id: 2,
  nome: "NVR 16 Canais",
  descricao: "Gravador de vídeo",
  preco: 1200,
  categoria: "CFTV",
  preco_base_fornecedor: null,
  imagem_url: "http://localhost:8000/img/nvr.jpg",
  imagens: [],
};

describe("AdminProdutosPage — carregamento inicial", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "mock-token", user: null });
    mockedFetchProducts.mockResolvedValue({ items: [PRODUTO_1, PRODUTO_2], total: 2 });
    mockedFetchCategories.mockResolvedValue(["CFTV", "Alarmes"]);
  });

  it("exibe o título da página", async () => {
    render(<AdminProdutosPage />);
    expect(await screen.findByText("Catálogo de Produtos")).toBeInTheDocument();
  });

  it("lista os produtos após carregar", async () => {
    render(<AdminProdutosPage />);
    expect(await screen.findByText("Câmera IP HD")).toBeInTheDocument();
    expect(screen.getByText("NVR 16 Canais")).toBeInTheDocument();
  });

  it("exibe o total de produtos no card de métricas", async () => {
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("exibe produtos com foto no card de métricas", async () => {
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    // PRODUTO_2 tem imagem_url, PRODUTO_1 não
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("exibe margem média quando há produtos com preco_base_fornecedor", async () => {
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    // PRODUTO_1: (450-300)/300 * 100 = 50%
    expect(screen.getByText("+50.0%")).toBeInTheDocument();
  });

  it("exibe '-' na margem quando nenhum produto tem preco_base_fornecedor", async () => {
    mockedFetchProducts.mockResolvedValue({ items: [PRODUTO_2], total: 1 });
    render(<AdminProdutosPage />);
    await screen.findByText("NVR 16 Canais");
    expect(screen.getByText("-")).toBeInTheDocument();
  });
});

describe("AdminProdutosPage — botões de ação", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "mock-token", user: null });
    mockedFetchProducts.mockResolvedValue({ items: [], total: 0 });
    mockedFetchCategories.mockResolvedValue([]);
  });

  it("abre o modal de novo produto ao clicar em 'Novo Produto'", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: /Novo Produto/ }));
    expect(screen.getByTestId("product-form-modal")).toBeInTheDocument();
    expect(screen.getByText("Novo produto")).toBeInTheDocument();
  });

  it("abre o modal de importação ao clicar em 'Importar Catálogo'", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: /Importar Catálogo/ }));
    expect(screen.getByTestId("catalog-import-modal")).toBeInTheDocument();
  });

  it("fecha o modal de novo produto ao clicar em fechar", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: /Novo Produto/ }));
    await user.click(screen.getByRole("button", { name: "Fechar modal" }));
    expect(screen.queryByTestId("product-form-modal")).not.toBeInTheDocument();
  });

  it("fecha o modal de importação ao clicar em fechar", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: /Importar Catálogo/ }));
    await user.click(screen.getByRole("button", { name: "Fechar importação" }));
    expect(screen.queryByTestId("catalog-import-modal")).not.toBeInTheDocument();
  });
});

describe("AdminProdutosPage — edição de produto", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "mock-token", user: null });
    mockedFetchProducts.mockResolvedValue({ items: [PRODUTO_1], total: 1 });
    mockedFetchCategories.mockResolvedValue(["CFTV"]);
  });

  it("abre o modal de edição com o produto correto ao clicar em Editar", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    await user.click(screen.getByRole("button", { name: "Editar Câmera IP HD" }));
    expect(screen.getByTestId("product-form-modal")).toBeInTheDocument();
    expect(screen.getByText("Editando: Câmera IP HD")).toBeInTheDocument();
  });
});

describe("AdminProdutosPage — exclusão de produto", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "mock-token", user: null });
    mockedFetchProducts.mockResolvedValue({ items: [PRODUTO_1], total: 1 });
    mockedFetchCategories.mockResolvedValue(["CFTV"]);
    mockedDeleteProduct.mockResolvedValue(undefined);
  });

  it("chama deleteAdminProduct e recarrega ao excluir", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    const chamantesAntes = mockedFetchProducts.mock.calls.length;
    await user.click(screen.getByRole("button", { name: "Excluir Câmera IP HD" }));
    expect(mockedDeleteProduct).toHaveBeenCalledWith("mock-token", 1);
    await waitFor(
      () => expect(mockedFetchProducts.mock.calls.length).toBeGreaterThan(chamantesAntes),
      { timeout: 2000 },
    );
  });

  it("exibe alert quando a exclusão falha", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => {});
    mockedDeleteProduct.mockRejectedValue(new Error("Erro de rede"));
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Câmera IP HD");
    await user.click(screen.getByRole("button", { name: "Excluir Câmera IP HD" }));
    await waitFor(() => expect(alertSpy).toHaveBeenCalled());
  });
});

describe("AdminProdutosPage — busca e filtros", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: "mock-token", user: null });
    mockedFetchProducts.mockResolvedValue({ items: [PRODUTO_1, PRODUTO_2], total: 2 });
    mockedFetchCategories.mockResolvedValue(["CFTV", "Alarmes"]);
  });

  it("exibe o campo de busca", async () => {
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    expect(
      screen.getByPlaceholderText(/Buscar por nome, modelo/),
    ).toBeInTheDocument();
  });

  it("exibe o CategoryFilter com as categorias disponíveis", async () => {
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    expect(screen.getByTestId("category-filter")).toBeInTheDocument();
  });

  it("exibe badges de filtros ativos ao selecionar categoria", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: "CFTV" }));
    expect(screen.getByText(/Filtros ativos/)).toBeInTheDocument();
  });

  it("remove badge ao clicar no ✕ do filtro ativo", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: "CFTV" }));
    expect(screen.getByText(/Filtros ativos/)).toBeInTheDocument();
    await user.click(screen.getByTitle("Remover filtro CFTV"));
    expect(screen.queryByText(/Filtros ativos/)).not.toBeInTheDocument();
  });

  it("limpa todos os filtros ao clicar em 'Limpar todas'", async () => {
    const user = userEvent.setup();
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    await user.click(screen.getByRole("button", { name: "CFTV" }));
    await user.click(screen.getByRole("button", { name: "Alarmes" }));
    expect(screen.getByText(/Filtros ativos \(2\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Limpar todas" }));
    expect(screen.queryByText(/Filtros ativos/)).not.toBeInTheDocument();
  });
});

describe("AdminProdutosPage — sem token", () => {
  it("não chama fetchAdminProducts quando token é null", async () => {
    mockedFetchProducts.mockClear();
    mockedFetchCategories.mockClear();
    useAuthStore.setState({ token: null, user: null });
    render(<AdminProdutosPage />);
    await screen.findByText("Catálogo de Produtos");
    expect(mockedFetchProducts).not.toHaveBeenCalled();
  });
});
