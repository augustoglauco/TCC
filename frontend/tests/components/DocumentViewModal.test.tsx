import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentViewModal } from "@/components/admin/DocumentViewModal";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    fetchDocumentContent: vi.fn(),
    getDocumentContentUrl: vi.fn((id: string) => `http://localhost:8000/api/rag/documents/${id}/content`),
  };
});

import { fetchDocumentContent } from "@/lib/api/rag";

const mockedFetchContent = vi.mocked(fetchDocumentContent);

function documento(overrides: Partial<DocumentRegistryEntry> = {}): DocumentRegistryEntry {
  return {
    id: "doc-1",
    filename: "manual.pdf",
    domain: "suporte",
    chunk_count: 3,
    collection_id: "col-1",
    collection_name: "docs_texto",
    origin: "upload",
    created_at: "2026-09-17T10:00:00Z",
    ...overrides,
  };
}

describe("DocumentViewModal", () => {
  beforeEach(() => {
    mockedFetchContent.mockReset();
    // jsdom não implementa createObjectURL/revokeObjectURL.
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn(() => "blob:fake-url"),
      revokeObjectURL: vi.fn(),
    });
  });

  it("não renderiza nada quando documento é null", () => {
    const { container } = render(<DocumentViewModal documento={null} onOpenChange={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("mostra estado de carregamento e depois o PDF num iframe", async () => {
    mockedFetchContent.mockImplementation(
      () => new Promise(() => {}), // nunca resolve — fica em loading
    );

    render(<DocumentViewModal documento={documento({ filename: "manual.pdf" })} onOpenChange={vi.fn()} />);

    expect(screen.getByText("Carregando documento...")).toBeInTheDocument();
  });

  it("renderiza o PDF num iframe usando um object URL do blob", async () => {
    const blob = new Blob(["%PDF-1.4 conteudo fake"], { type: "application/pdf" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "application/pdf" });

    render(<DocumentViewModal documento={documento({ filename: "manual.pdf" })} onOpenChange={vi.fn()} />);

    const iframe = await screen.findByTitle("manual.pdf");
    expect(iframe).toHaveAttribute("src", "blob:fake-url");
  });

  it("renderiza CSV como tabela com cabeçalho e linhas", async () => {
    const texto = "nome,preco\nGerador GD-30,1500\nAcessorio X,200";
    const blob = new Blob([texto], { type: "text/csv" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "text/csv", text: texto });

    render(
      <DocumentViewModal documento={documento({ filename: "produtos.csv" })} onOpenChange={vi.fn()} />,
    );

    expect(await screen.findByText("nome")).toBeInTheDocument();
    expect(screen.getByText("preco")).toBeInTheDocument();
    expect(screen.getByText("Gerador GD-30")).toBeInTheDocument();
    expect(screen.getByText("1500")).toBeInTheDocument();
  });

  it("respeita ; como delimitador e não corta campo entre aspas com ; dentro (regressão)", async () => {
    // Bug corrigido: o parser antigo cortava em QUALQUER espaço em branco
    // dentro do campo (independente de aspas), então "Gerador; a diesel"
    // virava duas células. Também nunca usava o delimitador detectado de
    // verdade — cortava sempre em vírgula OU ponto e vírgula.
    const texto = 'nome;descricao\n"Gerador; a diesel";30 kVA';
    const blob = new Blob([texto], { type: "text/csv" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "text/csv", text: texto });

    render(
      <DocumentViewModal documento={documento({ filename: "produtos.csv" })} onOpenChange={vi.fn()} />,
    );

    expect(await screen.findByText("Gerador; a diesel")).toBeInTheDocument();
    expect(screen.getByText("30 kVA")).toBeInTheDocument();
  });

  it("renderiza texto puro para .txt/.md", async () => {
    const texto = "Manual de instruções do gerador GD-30.";
    const blob = new Blob([texto], { type: "text/plain" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "text/plain", text: texto });

    render(<DocumentViewModal documento={documento({ filename: "manual.txt" })} onOpenChange={vi.fn()} />);

    expect(await screen.findByText(texto)).toBeInTheDocument();
  });

  it("mostra mensagem de erro quando a busca do conteúdo falha", async () => {
    mockedFetchContent.mockRejectedValueOnce(new Error("Não foi possível carregar o conteúdo."));

    render(<DocumentViewModal documento={documento()} onOpenChange={vi.fn()} />);

    expect(await screen.findByText("Não foi possível carregar o conteúdo.")).toBeInTheDocument();
  });

  it("link de download aponta para a URL de conteúdo do documento", async () => {
    const blob = new Blob(["conteudo"], { type: "text/plain" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "text/plain", text: "conteudo" });

    render(<DocumentViewModal documento={documento({ id: "doc-42" })} onOpenChange={vi.fn()} />);

    await waitFor(() => {
      expect(screen.queryByText("Carregando documento...")).not.toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /Baixar original/ });
    expect(link).toHaveAttribute("href", "http://localhost:8000/api/rag/documents/doc-42/content");
  });

  it("revoga o object URL do blob anterior ao fechar (documento vira null)", async () => {
    const blob = new Blob(["%PDF-1.4"], { type: "application/pdf" });
    mockedFetchContent.mockResolvedValueOnce({ blob, contentType: "application/pdf" });

    const { rerender } = render(
      <DocumentViewModal documento={documento({ filename: "manual.pdf" })} onOpenChange={vi.fn()} />,
    );
    await screen.findByTitle("manual.pdf");

    rerender(<DocumentViewModal documento={null} onOpenChange={vi.fn()} />);

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:fake-url");
  });
});
