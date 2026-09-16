import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentsTable } from "@/components/admin/DocumentsTable";
import { RagApiError } from "@/lib/api/rag";
import type { DocumentRegistryEntry, RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, deleteDocument: vi.fn(), reingestDocument: vi.fn() };
});

import { deleteDocument } from "@/lib/api/rag";

const mockedDeleteDocument = vi.mocked(deleteDocument);

const COLLECTION: RagCollection = {
  id: "col-1",
  name: "docs_texto",
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2",
  vector_dimension: 384,
  distance_metric: "cosine",
  chunk_size: 800,
  chunk_overlap: 100,
  hnsw_m: 16,
  hnsw_ef_construct: 100,
  hnsw_full_scan_threshold: 10000,
  hnsw_max_indexing_threads: 0,
  hnsw_on_disk: false,
  hnsw_payload_m: null,
  quantization_type: "none",
  quantization_config: {},
  payload_indexes: [],
  is_active: true,
  document_count: 1,
  created_at: new Date().toISOString(),
};

const DOCUMENTO: DocumentRegistryEntry = {
  id: "11111111-1111-1111-1111-111111111111",
  filename: "catalogo.txt",
  domain: "vendas",
  chunk_count: 3,
  collection_id: "col-1",
  collection_name: "docs_texto",
  origin: "upload",
  created_at: new Date().toISOString(),
};

describe("DocumentsTable", () => {
  beforeEach(() => {
    mockedDeleteDocument.mockReset();
  });

  it("renderiza uma linha por documento, com a collection", () => {
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    expect(screen.getByText("catalogo.txt")).toBeInTheDocument();
    expect(screen.getByText("Vendas")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("docs_texto")).toBeInTheDocument();
  });

  it("clicar em excluir abre o modal, e cancelar não chama a API", async () => {
    const user = userEvent.setup();
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    expect(screen.getByText(/tem certeza/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(mockedDeleteDocument).not.toHaveBeenCalled();
  });

  it("confirmar a exclusão chama a API e notifica onDeleted", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockResolvedValueOnce(undefined);
    const onDeleted = vi.fn();
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={onDeleted} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDeleteDocument).toHaveBeenCalledWith(DOCUMENTO.id);
    expect(await screen.findByText(/excluído/i)).toBeInTheDocument();
    expect(onDeleted).toHaveBeenCalledWith(DOCUMENTO.id);
  });

  it("exibe erro quando a exclusão falha", async () => {
    const user = userEvent.setup();
    mockedDeleteDocument.mockRejectedValueOnce(new RagApiError("Não foi possível excluir."));
    render(
      <DocumentsTable documents={[DOCUMENTO]} collections={[COLLECTION]} onDeleted={vi.fn()} onReingested={vi.fn()} />,
    );

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(await screen.findByText("Não foi possível excluir.")).toBeInTheDocument();
  });

  it("clicar em reingerir abre o modal de reingestão", async () => {
    const user = userEvent.setup();
    const outraCollection: RagCollection = { ...COLLECTION, id: "col-2", name: "outra" };
    render(
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION, outraCollection]}
        onDeleted={vi.fn()}
        onReingested={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Reingerir" }));

    expect(screen.getByText("Reingerir em outra collection")).toBeInTheDocument();
  });
});
