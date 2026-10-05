import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CatalogImportModal from "@/components/admin/products/CatalogImportModal";
import { useAuthStore } from "@/lib/hooks/useAuthStore";

beforeEach(() => {
  useAuthStore.setState({
    user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
    token: "mock-token-1",
  });
});

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
    render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.queryByLabelText(/Intervalo de Páginas do PDF/i)).not.toBeInTheDocument();

    const imageFile = new File(["dummy"], "produto.jpg", { type: "image/jpeg" });
    const fileInput = document.getElementById("catalog-file-upload") as HTMLInputElement;
    fireEvent.change(fileInput, { target: { files: [imageFile] } });

    expect(screen.queryByLabelText(/Intervalo de Páginas do PDF/i)).not.toBeInTheDocument();
  });

  it("exibe o campo de intervalo de páginas quando um arquivo PDF é selecionado e repassa o range na extração", async () => {
    const user = userEvent.setup();
    render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);

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
      "mock-token-1",
      [pdfFile],
      expect.objectContaining({
        pageRange: "1-5, 8",
        provider: "local",
      }),
      expect.any(Object),
    );
  });

  it("permite iniciar extração sem informar intervalo (deixando em branco para todas as páginas)", async () => {
    const user = userEvent.setup();
    render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);

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
      "mock-token-1",
      [pdfFile],
      expect.objectContaining({
        pageRange: undefined,
      }),
      expect.any(Object),
    );
  });
});

describe("CatalogImportModal - arrastar, colar e tipos de arquivo", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function renderModal() {
    return render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);
  }

  it("aceita PDF, imagem e texto soltos sobre o modal e acumula com os já selecionados", async () => {
    renderModal();
    const pdf = new File(["x"], "tabela.pdf", { type: "application/pdf" });
    const foto = new File(["x"], "folheto.png", { type: "image/png" });
    const texto = new File(["x"], "lista.csv", { type: "text/csv" });

    fireEvent.drop(screen.getByTestId("catalog-dropzone"), { dataTransfer: { files: [pdf] } });
    fireEvent.drop(screen.getByTestId("catalog-dropzone"), {
      dataTransfer: { files: [foto, texto] },
    });

    expect(await screen.findByText("tabela.pdf")).toBeInTheDocument();
    expect(screen.getByText("folheto.png")).toBeInTheDocument();
    expect(screen.getByText("lista.csv")).toBeInTheDocument();
    expect(screen.getByLabelText(/Intervalo de Páginas do PDF/i)).toBeInTheDocument();
  });

  it("destaca a área enquanto arrasta e remove o destaque ao soltar", () => {
    renderModal();
    const zona = screen.getByTestId("catalog-dropzone");

    fireEvent.dragOver(zona, { dataTransfer: { files: [] } });
    expect(screen.getByText(/Solte os arquivos aqui/i)).toBeInTheDocument();

    fireEvent.drop(zona, { dataTransfer: { files: [] } });
    expect(screen.queryByText(/Solte os arquivos aqui/i)).not.toBeInTheDocument();
  });

  it("rejeita tipos não suportados com aviso e não os adiciona", () => {
    renderModal();
    const zip = new File(["x"], "catalogo.zip", { type: "application/zip" });

    fireEvent.drop(screen.getByTestId("catalog-dropzone"), { dataTransfer: { files: [zip] } });

    expect(screen.getByText(/Tipo não suportado: catalogo\.zip/i)).toBeInTheDocument();
    expect(screen.queryByText("catalogo.zip", { selector: "span" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Iniciar Extração Inteligente/i })).toBeDisabled();
  });

  it("cola uma imagem da área de transferência com nome único", async () => {
    renderModal();
    const imagem = new File(["x"], "image.png", { type: "image/png" });

    fireEvent.paste(document, {
      clipboardData: { files: [imagem], items: [], getData: () => "" },
    });

    expect(await screen.findByText(/^imagem-colada-\d+-0\.png$/)).toBeInTheDocument();
  });

  it("cola texto copiado como arquivo .txt e o envia na extração", async () => {
    const user = userEvent.setup();
    renderModal();

    fireEvent.paste(document, {
      clipboardData: { files: [], items: [], getData: () => "Câmera Bullet R$ 320,00" },
    });

    expect(await screen.findByText(/^texto-colado-\d+\.txt$/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Iniciar Extração Inteligente/i }));

    const enviados = mockedExtractStream.mock.calls[0][1];
    expect(enviados).toHaveLength(1);
    expect(enviados[0].name).toMatch(/^texto-colado-\d+\.txt$/);
    const conteudo = await new Promise<string>((resolve) => {
      const leitor = new FileReader();
      leitor.onload = () => resolve(String(leitor.result));
      leitor.readAsText(enviados[0]);
    });
    expect(conteudo).toBe("Câmera Bullet R$ 320,00");
  });

  it("não intercepta a colagem dentro de um campo de texto", async () => {
    const user = userEvent.setup();
    renderModal();
    fireEvent.change(document.getElementById("catalog-file-upload") as HTMLInputElement, {
      target: { files: [new File(["x"], "t.pdf", { type: "application/pdf" })] },
    });

    const campo = await screen.findByLabelText(/Intervalo de Páginas do PDF/i);
    await user.click(campo);
    fireEvent.paste(campo, {
      clipboardData: { files: [], items: [], getData: () => "1-3" },
    });

    expect(screen.queryByText(/^texto-colado-/)).not.toBeInTheDocument();
  });

  it("permite remover um arquivo da lista", async () => {
    const user = userEvent.setup();
    renderModal();
    const a = new File(["x"], "a.txt", { type: "text/plain" });
    const b = new File(["y"], "b.txt", { type: "text/plain" });
    fireEvent.drop(screen.getByTestId("catalog-dropzone"), { dataTransfer: { files: [a, b] } });

    await user.click(await screen.findByRole("button", { name: "Remover a.txt" }));

    expect(screen.queryByText("a.txt")).not.toBeInTheDocument();
    expect(screen.getByText("b.txt")).toBeInTheDocument();
  });
});

describe("CatalogImportModal - erro de extração por página", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mostra o erro da página (ex.: visão externa indisponível) em vez de 'nenhum produto encontrado'", async () => {
    const user = userEvent.setup();
    mockedExtractStream.mockImplementation(async (_token, _files, _opts, handlers) => {
      handlers.onPageComplete?.({
        pagina: 1,
        total_paginas: 1,
        produtos: [],
        provider_usado: "external",
        erro: "Falha ao consultar modelo de visão externo: 429 Too Many Requests",
      });
      handlers.onDone?.({ total_produtos: 0, total_paginas: 1 });
    });

    render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);
    const foto = new File(["x"], "folheto.png", { type: "image/png" });
    fireEvent.drop(screen.getByTestId("catalog-dropzone"), { dataTransfer: { files: [foto] } });

    await user.click(screen.getByRole("button", { name: /Iniciar Extração Inteligente/i }));

    expect(
      await screen.findByText(/Página 1: Falha ao consultar modelo de visão externo/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Nenhum produto foi extraído — corrija o problema acima/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/^Nenhum produto foi detectado nos arquivos/i),
    ).not.toBeInTheDocument();
  });

  it("não mostra aviso de erro quando a extração simplesmente não encontra produtos", async () => {
    const user = userEvent.setup();
    mockedExtractStream.mockImplementation(async (_token, _files, _opts, handlers) => {
      handlers.onPageComplete?.({
        pagina: 1,
        total_paginas: 1,
        produtos: [],
        provider_usado: "local",
      });
      handlers.onDone?.({ total_produtos: 0, total_paginas: 1 });
    });

    render(<CatalogImportModal isOpen={true} onClose={vi.fn()} onSuccess={vi.fn()} />);
    const texto = new File(["x"], "lista.csv", { type: "text/csv" });
    fireEvent.drop(screen.getByTestId("catalog-dropzone"), { dataTransfer: { files: [texto] } });

    await user.click(screen.getByRole("button", { name: /Iniciar Extração Inteligente/i }));

    expect(
      await screen.findByText(/^Nenhum produto foi detectado nos arquivos fornecidos\.$/i),
    ).toBeInTheDocument();
  });
});
