import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CatalogImportModal from "@/components/admin/products/CatalogImportModal";

vi.mock("@/lib/api/adminProducts", () => ({
  extractCatalogStream: vi.fn(),
  confirmCatalogExtraction: vi.fn(),
  uploadTempImage: vi.fn(),
}));

import { extractCatalogStream } from "@/lib/api/adminProducts";

const mockedExtractStream = vi.mocked(extractCatalogStream);

describe("CatalogImportModal - Intervalo de Páginas", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("não exibe campo de intervalo de páginas se nenhum arquivo ou apenas imagem estiver selecionado", () => {
    render(
      <CatalogImportModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    expect(screen.queryByLabelText(/Intervalo de Páginas do PDF/i)).not.toBeInTheDocument();

    const imageFile = new File(["dummy"], "produto.jpg", { type: "image/jpeg" });
    const fileInput = document.getElementById("catalog-file-upload") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [imageFile] } });

    expect(screen.queryByLabelText(/Intervalo de Páginas do PDF/i)).not.toBeInTheDocument();
  });

  it("exibe o campo de intervalo de páginas quando um arquivo PDF é selecionado e repassa o range na extração", async () => {
    const user = userEvent.setup();
    render(
      <CatalogImportModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    const pdfFile = new File(["dummy pdf content"], "tabela_precos.pdf", {
      type: "application/pdf",
    });
    const fileInput = document.getElementById("catalog-file-upload") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    const rangeInput = await screen.findByLabelText(/Intervalo de Páginas do PDF/i);
    expect(rangeInput).toBeInTheDocument();

    await user.type(rangeInput, "1-5, 8");

    const startButton = screen.getByRole("button", {
      name: /Iniciar Extração Inteligente/i,
    });
    await user.click(startButton);

    expect(mockedExtractStream).toHaveBeenCalledWith(
      [pdfFile],
      expect.objectContaining({
        pageRange: "1-5, 8",
        provider: "local",
      }),
      expect.any(Object)
    );
  });

  it("permite iniciar extração sem informar intervalo (deixando em branco para todas as páginas)", async () => {
    const user = userEvent.setup();
    render(
      <CatalogImportModal
        isOpen={true}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
      />
    );

    const pdfFile = new File(["dummy pdf content"], "catalogo_completo.pdf", {
      type: "application/pdf",
    });
    const fileInput = document.getElementById("catalog-file-upload") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [pdfFile] } });

    expect(await screen.findByLabelText(/Intervalo de Páginas do PDF/i)).toBeInTheDocument();

    const startButton = screen.getByRole("button", {
      name: /Iniciar Extração Inteligente/i,
    });
    await user.click(startButton);

    expect(mockedExtractStream).toHaveBeenCalledWith(
      [pdfFile],
      expect.objectContaining({
        pageRange: undefined,
      }),
      expect.any(Object)
    );
  });
});
