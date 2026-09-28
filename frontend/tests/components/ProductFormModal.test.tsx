import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProductFormModal from "@/components/admin/products/ProductFormModal";
import type { AdminProduct } from "@/lib/types/adminProducts";

vi.mock("@/lib/api/adminProducts", () => ({
  createAdminProduct: vi.fn(),
  updateAdminProduct: vi.fn(),
  uploadAdminProductImage: vi.fn(),
  deleteAdminProductImage: vi.fn(),
  fetchAdminProduct: vi.fn(),
  updateAdminProductStock: vi.fn(),
  addAdminProductVolumeDiscount: vi.fn(),
  deleteAdminProductVolumeDiscount: vi.fn(),
  fetchAdminProductCompatibilities: vi.fn().mockResolvedValue([]),
  addAdminProductCompatibility: vi.fn().mockResolvedValue([]),
  deleteAdminProductCompatibility: vi.fn().mockResolvedValue([]),
}));

import { deleteAdminProductImage, fetchAdminProduct } from "@/lib/api/adminProducts";

const mockedDeleteImage = vi.mocked(deleteAdminProductImage);
const mockedFetchProduct = vi.mocked(fetchAdminProduct);

const PRODUTO_MOCK: AdminProduct = {
  id: 42,
  nome: "Câmera Bullet IP",
  categoria: "CFTV",
  preco: 299.9,
  preco_base_fornecedor: 180.0,
  descricao: "Câmera infravermelho resistente à água",
  especificacoes_tecnicas: "1080p, IP67",
  imagem_url: "/api/uploads/produtos/foto1.jpg",
  imagens: [
    {
      id: 101,
      produto_id: 42,
      imagem_url: "/api/uploads/produtos/foto1.jpg",
      clip_image_id: "clip-101",
      is_principal: true,
      criado_em: "2026-09-25T10:00:00Z",
    },
    {
      id: 102,
      produto_id: 42,
      imagem_url: "/api/uploads/produtos/foto2.jpg",
      clip_image_id: "clip-102",
      is_principal: false,
      criado_em: "2026-09-25T10:05:00Z",
    },
  ],
};

describe("ProductFormModal - Exclusão e Atualização de Imagens", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("exibe lista de imagens associadas ao produto", () => {
    render(
      <ProductFormModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        produtoParaEditar={PRODUTO_MOCK}
      />,
    );

    expect(screen.getByText("Imagens associadas (2):")).toBeInTheDocument();
    const deleteButtons = screen.getAllByTitle("Remover imagem do produto e do CLIP");
    expect(deleteButtons).toHaveLength(2);
  });

  it("ao excluir uma imagem, atualiza a área de imagens e chama deleteAdminProductImage", async () => {
    const user = userEvent.setup();
    mockedDeleteImage.mockResolvedValueOnce(undefined);

    const produtoAtualizado: AdminProduct = {
      ...PRODUTO_MOCK,
      imagem_url: "/api/uploads/produtos/foto2.jpg",
      imagens: [PRODUTO_MOCK.imagens![1]],
    };
    mockedFetchProduct.mockResolvedValueOnce(produtoAtualizado);

    const onSuccess = vi.fn();

    render(
      <ProductFormModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={onSuccess}
        produtoParaEditar={PRODUTO_MOCK}
      />,
    );

    const deleteButtons = screen.getAllByTitle("Remover imagem do produto e do CLIP");
    await user.click(deleteButtons[0]);

    expect(mockedDeleteImage).toHaveBeenCalledWith(42, 101);

    await waitFor(() => {
      expect(screen.getByText("Imagens associadas (1):")).toBeInTheDocument();
    });

    expect(screen.getAllByTitle("Remover imagem do produto e do CLIP")).toHaveLength(1);
    expect(onSuccess).toHaveBeenCalledWith(produtoAtualizado);
  });

  it("quando a única imagem é excluída, limpa a área de imagens e o preview", async () => {
    const user = userEvent.setup();
    mockedDeleteImage.mockResolvedValueOnce(undefined);

    const produtoComUmaImagem: AdminProduct = {
      ...PRODUTO_MOCK,
      imagens: [PRODUTO_MOCK.imagens![0]],
    };

    const produtoSemImagens: AdminProduct = {
      ...PRODUTO_MOCK,
      imagem_url: null,
      imagens: [],
    };
    mockedFetchProduct.mockResolvedValueOnce(produtoSemImagens);

    const onSuccess = vi.fn();

    render(
      <ProductFormModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={onSuccess}
        produtoParaEditar={produtoComUmaImagem}
      />,
    );

    expect(screen.getByText("Imagens associadas (1):")).toBeInTheDocument();
    const deleteBtn = screen.getByTitle("Remover imagem do produto e do CLIP");
    await user.click(deleteBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Imagens associadas/)).not.toBeInTheDocument();
    });

    expect(screen.queryByAltText("Preview")).not.toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalledWith(produtoSemImagens);
  });

  it("preserva alterações no formulário (ex: nome alterado) ao excluir uma imagem", async () => {
    const user = userEvent.setup();
    mockedDeleteImage.mockResolvedValueOnce(undefined);
    mockedFetchProduct.mockResolvedValueOnce({
      ...PRODUTO_MOCK,
      imagens: [PRODUTO_MOCK.imagens![1]],
    });

    render(
      <ProductFormModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        produtoParaEditar={PRODUTO_MOCK}
      />,
    );

    const nomeInput = screen.getByPlaceholderText("Ex: Gravador IP NVD 1016");
    await user.clear(nomeInput);
    await user.type(nomeInput, "Nome Editado Manualmente");

    const deleteButtons = screen.getAllByTitle("Remover imagem do produto e do CLIP");
    await user.click(deleteButtons[0]);

    await waitFor(() => {
      expect(screen.getByText("Imagens associadas (1):")).toBeInTheDocument();
    });

    // O nome digitado não deve ter sido apagado ou resetado
    expect(nomeInput).toHaveValue("Nome Editado Manualmente");
  });

  it("exibe mensagem de erro e faz rollback da imagem caso a exclusão falhe", async () => {
    const user = userEvent.setup();
    mockedDeleteImage.mockRejectedValueOnce(new Error("Falha na conexão com o servidor"));

    render(
      <ProductFormModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        produtoParaEditar={PRODUTO_MOCK}
      />,
    );

    const deleteButtons = screen.getAllByTitle("Remover imagem do produto e do CLIP");
    await user.click(deleteButtons[0]);

    expect(await screen.findByText("Falha na conexão com o servidor")).toBeInTheDocument();

    // A imagem que falhou ao ser removida deve voltar para a lista
    expect(screen.getByText("Imagens associadas (2):")).toBeInTheDocument();
  });
});
