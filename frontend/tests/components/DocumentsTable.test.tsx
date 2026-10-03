import { render, screen, within } from "@testing-library/react";
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
  purpose: "chat",
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
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION]}
        onDeleted={vi.fn()}
        onReingested={vi.fn()}
      />,
    );

    expect(screen.getByText("catalogo.txt")).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Vendas")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("docs_texto")).toBeInTheDocument();
  });

  it("clicar em excluir abre o modal, e cancelar não chama a API", async () => {
    const user = userEvent.setup();
    render(
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION]}
        onDeleted={vi.fn()}
        onReingested={vi.fn()}
      />,
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
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION]}
        onDeleted={onDeleted}
        onReingested={vi.fn()}
      />,
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
      <DocumentsTable
        documents={[DOCUMENTO]}
        collections={[COLLECTION]}
        onDeleted={vi.fn()}
        onReingested={vi.fn()}
      />,
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

  describe("Filtros de documentos", () => {
    const DOC_VENDAS: DocumentRegistryEntry = {
      id: "doc-1",
      filename: "catalogo_produtos.pdf",
      domain: "vendas",
      chunk_count: 5,
      collection_id: "col-1",
      collection_name: "docs_texto",
      origin: "upload",
      created_at: "2026-09-15T10:00:00Z",
    };

    const DOC_SUPORTE: DocumentRegistryEntry = {
      id: "doc-2",
      filename: "manual_tecnico_cftv.pdf",
      domain: "suporte",
      chunk_count: 12,
      collection_id: "col-2",
      collection_name: "docs_suporte",
      origin: "upload",
      created_at: "2026-09-25T14:30:00Z",
    };

    const DOC_ATENDIMENTO: DocumentRegistryEntry = {
      id: "doc-3",
      filename: "politica_trocas.txt",
      domain: "atendimento",
      chunk_count: 2,
      collection_id: "col-1",
      collection_name: "docs_texto",
      origin: "upload",
      created_at: "2026-10-02T08:00:00Z",
    };

    const COLLECTIONS = [
      COLLECTION,
      { ...COLLECTION, id: "col-2", name: "docs_suporte" },
    ];

    it("filtra por nome do arquivo (case-insensitive)", async () => {
      const user = userEvent.setup();
      render(
        <DocumentsTable
          documents={[DOC_VENDAS, DOC_SUPORTE, DOC_ATENDIMENTO]}
          collections={COLLECTIONS}
          onDeleted={vi.fn()}
          onReingested={vi.fn()}
        />,
      );

      expect(screen.getByText("catalogo_produtos.pdf")).toBeInTheDocument();
      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.getByText("politica_trocas.txt")).toBeInTheDocument();

      const inputBusca = screen.getByPlaceholderText(/Buscar por nome do arquivo/i);
      await user.type(inputBusca, "manual");

      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.queryByText("catalogo_produtos.pdf")).not.toBeInTheDocument();
      expect(screen.queryByText("politica_trocas.txt")).not.toBeInTheDocument();
    });

    it("filtra por domínio(s) permitindo seleção múltipla", async () => {
      const user = userEvent.setup();
      render(
        <DocumentsTable
          documents={[DOC_VENDAS, DOC_SUPORTE, DOC_ATENDIMENTO]}
          collections={COLLECTIONS}
          onDeleted={vi.fn()}
          onReingested={vi.fn()}
        />,
      );

      // Clica no filtro de 'Suporte Técnico'
      const btnSuporte = screen.getByRole("button", { name: /^Suporte/i });
      await user.click(btnSuporte);

      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.queryByText("catalogo_produtos.pdf")).not.toBeInTheDocument();
      expect(screen.queryByText("politica_trocas.txt")).not.toBeInTheDocument();

      // Ativa também 'Vendas'
      const btnVendas = screen.getByRole("button", { name: /^Vendas/i });
      await user.click(btnVendas);

      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.getByText("catalogo_produtos.pdf")).toBeInTheDocument();
      expect(screen.queryByText("politica_trocas.txt")).not.toBeInTheDocument();
    });

    it("filtra por collection", async () => {
      const user = userEvent.setup();
      render(
        <DocumentsTable
          documents={[DOC_VENDAS, DOC_SUPORTE, DOC_ATENDIMENTO]}
          collections={COLLECTIONS}
          onDeleted={vi.fn()}
          onReingested={vi.fn()}
        />,
      );

      const selectCollection = screen.getByLabelText(/Collection/i);
      await user.selectOptions(selectCollection, "col-2");

      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.queryByText("catalogo_produtos.pdf")).not.toBeInTheDocument();
      expect(screen.queryByText("politica_trocas.txt")).not.toBeInTheDocument();
    });

    it("filtra por range de data de criação", async () => {
      const { fireEvent } = await import("@testing-library/react");
      render(
        <DocumentsTable
          documents={[DOC_VENDAS, DOC_SUPORTE, DOC_ATENDIMENTO]}
          collections={COLLECTIONS}
          onDeleted={vi.fn()}
          onReingested={vi.fn()}
        />,
      );

      const inputDe = screen.getByLabelText(/De:/i);
      const inputAte = screen.getByLabelText(/Até:/i);

      // Filtra documentos criados entre 2026-09-20 e 2026-09-30
      fireEvent.change(inputDe, { target: { value: "2026-09-20" } });
      fireEvent.change(inputAte, { target: { value: "2026-09-30" } });

      // DOC_SUPORTE (2026-09-25) deve estar visível
      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      // DOC_VENDAS (2026-09-15) e DOC_ATENDIMENTO (2026-10-02) devem estar ocultos
      expect(screen.queryByText("catalogo_produtos.pdf")).not.toBeInTheDocument();
      expect(screen.queryByText("politica_trocas.txt")).not.toBeInTheDocument();
    });

    it("botão limpar filtros restaura a lista completa", async () => {
      const user = userEvent.setup();
      render(
        <DocumentsTable
          documents={[DOC_VENDAS, DOC_SUPORTE, DOC_ATENDIMENTO]}
          collections={COLLECTIONS}
          onDeleted={vi.fn()}
          onReingested={vi.fn()}
        />,
      );

      const inputBusca = screen.getByPlaceholderText(/Buscar por nome do arquivo/i);
      await user.type(inputBusca, "termo_inexistente");

      expect(screen.getByText(/Nenhum documento encontrado com os filtros selecionados/i)).toBeInTheDocument();

      const btnLimpar = screen.getAllByRole("button", { name: /Limpar filtros/i })[0];
      await user.click(btnLimpar);

      expect(screen.getByText("catalogo_produtos.pdf")).toBeInTheDocument();
      expect(screen.getByText("manual_tecnico_cftv.pdf")).toBeInTheDocument();
      expect(screen.getByText("politica_trocas.txt")).toBeInTheDocument();
    });
  });
});
