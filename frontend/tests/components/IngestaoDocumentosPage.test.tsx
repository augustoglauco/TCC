import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestaoDocumentosPage from "@/app/admin/ingestao/page";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    uploadDocument: vi.fn(),
    listDocuments: vi.fn(),
  };
});

import { listDocuments, uploadDocument } from "@/lib/api/rag";

const mockedUploadDocument = vi.mocked(uploadDocument);
const mockedListDocuments = vi.mocked(listDocuments);

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  chunk_size: 800,
  chunk_overlap: 100,
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("IngestaoDocumentosPage", () => {
  beforeEach(() => {
    mockedUploadDocument.mockReset();
    mockedListDocuments.mockReset();
    mockedListDocuments.mockResolvedValue([]);
  });

  it("envia o arquivo selecionado e exibe o resultado da ingestão", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockResolvedValueOnce({
      filename: "catalogo.txt",
      domain: "vendas",
      chunks: 3,
    });

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/3 chunk\(s\) gravado\(s\)/)).toBeInTheDocument();
    expect(mockedUploadDocument).toHaveBeenCalledWith({ file, domain: "vendas" });
  });

  it("exibe mensagem de erro quando o upload falha", async () => {
    const user = userEvent.setup();
    mockedUploadDocument.mockRejectedValueOnce(
      new RagApiError("Serviço de RAG temporariamente indisponível. Tente novamente.", 503),
    );

    render(<IngestaoDocumentosPage />);

    const file = new File(["conteudo"], "catalogo.txt", { type: "text/plain" });
    await user.upload(screen.getByLabelText("Arquivo"), file);
    await user.click(screen.getByRole("button", { name: "Enviar para ingestão" }));

    expect(await screen.findByText(/temporariamente indisponível/)).toBeInTheDocument();
  });

  it("desabilita o envio enquanto nenhum arquivo foi selecionado", () => {
    render(<IngestaoDocumentosPage />);

    expect(screen.getByRole("button", { name: "Enviar para ingestão" })).toBeDisabled();
  });

  it("aba 'Documentos ingeridos' lista os documentos ao ser aberta", async () => {
    const user = userEvent.setup();
    mockedListDocuments.mockResolvedValue([DOCUMENTO]);

    render(<IngestaoDocumentosPage />);
    await user.click(screen.getByRole("tab", { name: "Documentos ingeridos" }));

    expect(await screen.findByText("catalogo.txt")).toBeInTheDocument();
  });

  it("aba 'Configuração' aparece desabilitada", () => {
    render(<IngestaoDocumentosPage />);

    expect(screen.getByRole("tab", { name: "Configuração" })).toBeDisabled();
  });
});
