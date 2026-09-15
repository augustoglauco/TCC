import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, deleteDocument: vi.fn() };
});

import { deleteDocument } from "@/lib/api/rag";

const mockedDeleteDocument = vi.mocked(deleteDocument);

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

describe("DocumentsTable", () => {
  beforeEach(() => {
    mockedDeleteDocument.mockReset();
  });

  it("renderiza uma linha por documento", () => {
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    expect(screen.getByText("catalogo.txt")).toBeInTheDocument();
    expect(screen.getByText("Vendas")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("clicar em excluir abre o modal, e cancelar não chama a API", async () => {
    const user = userEvent.setup();
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(/tem certeza/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(mockedDeleteDocument).not.toHaveBeenCalled();
  });

  it("confirmar a exclusão chama a API e notifica onDeleted", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={onDeleted} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDeleteDocument).toHaveBeenCalledWith(DOCUMENTO.id);
    expect(await screen.findByText(/excluído/i)).toBeInTheDocument();
    expect(onDeleted).toHaveBeenCalledWith(DOCUMENTO.id);
  });

  it("exibe erro quando a exclusão falha", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockRejectedValueOnce(new RagApiError("Não foi possível excluir."));
    render(<DocumentsTable documents={[DOCUMENTO]} onDeleted={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(await screen.findByText("Não foi possível excluir.")).toBeInTheDocument();
  });
});
