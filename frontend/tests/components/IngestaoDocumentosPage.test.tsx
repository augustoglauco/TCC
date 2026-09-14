import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestaoDocumentosPage from "@/app/admin/ingestao/page";
import { RagApiError } from "@/lib/api/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    uploadDocument: vi.fn(),
  };
});

import { uploadDocument } from "@/lib/api/rag";

const mockedUploadDocument = vi.mocked(uploadDocument);

describe("IngestaoDocumentosPage", () => {
  beforeEach(() => {
    mockedUploadDocument.mockReset();
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
    // Regressão: `form.reset()` já causou "Erro inesperado ao enviar o
    // documento" aparecer junto com o resultado de sucesso (bug real,
    // encontrado só em teste manual no navegador — `event.currentTarget`
    // fica `null` após o `await`, ver comentário em `handleSubmit`).
    expect(screen.queryByText(/Erro inesperado/)).not.toBeInTheDocument();
  });

  it("exibe mensagem de erro quando o upload falha", async () => {
    // MVP: `accept=".txt,.md,.pdf"` no input já impede escolher um arquivo
    // de extensão não suportada pelo seletor nativo do navegador (e do
    // `user.upload` do Testing Library) — por isso o cenário de erro
    // exercitado aqui é o backend indisponível (503), não formato inválido
    // (esse já é coberto no backend, ver `test_rag_api.py`).
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
});
