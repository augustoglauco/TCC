import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CollectionsTable } from "@/components/admin/CollectionsTable";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, activateCollection: vi.fn(), deleteCollection: vi.fn() };
});

import { activateCollection, deleteCollection, RagApiError } from "@/lib/api/rag";

const mockedActivate = vi.mocked(activateCollection);
const mockedDelete = vi.mocked(deleteCollection);

const COLLECTION_ATIVA: RagCollection = {
  id: "11111111-1111-1111-1111-111111111111",
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
  document_count: 3,
  created_at: new Date().toISOString(),
};

const COLLECTION_INATIVA: RagCollection = { ...COLLECTION_ATIVA, id: "222", name: "teste", is_active: false, document_count: 1 };

const COLLECTION_MCP: RagCollection = { ...COLLECTION_ATIVA, id: "333", name: "mcp_docs", is_active: false, purpose: "mcp_b2b", document_count: 2 };

describe("CollectionsTable", () => {
  beforeEach(() => {
    mockedActivate.mockReset();
    mockedDelete.mockReset();
  });

  it("renderiza uma linha por collection, com badge 'Ativa'", () => {
    render(<CollectionsTable collections={[COLLECTION_ATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText("docs_texto")).toBeInTheDocument();
    expect(screen.getByText("Ativa")).toBeInTheDocument();
  });

  it("collection mcp_b2b mostra badge 'MCP B2B' e botão Ativar desabilitado", () => {
    render(<CollectionsTable collections={[COLLECTION_MCP]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByText("MCP B2B")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ativar" })).toBeDisabled();
  });

  it("não chama a API ao clicar em Ativar de uma collection mcp_b2b (botão desabilitado)", async () => {
    const user = userEvent.setup();
    render(<CollectionsTable collections={[COLLECTION_MCP]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).not.toHaveBeenCalled();
  });

  it("botão excluir da collection ativa fica desabilitado", () => {
    render(<CollectionsTable collections={[COLLECTION_ATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Excluir" })).toBeDisabled();
  });

  it("clicar em ativar chama a API e notifica onChanged/onSuccess", async () => {
    const user = userEvent.setup();
    mockedActivate.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    const onSuccess = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={onChanged} onError={vi.fn()} onSuccess={onSuccess} />);

    await user.click(screen.getByRole("button", { name: "Ativar" }));

    expect(mockedActivate).toHaveBeenCalledWith("222");
    expect(onChanged).toHaveBeenCalled();
    expect(onSuccess).toHaveBeenCalled();
  });

  it("excluir uma collection inativa abre modal de confirmação com a contagem de documentos", async () => {
    const user = userEvent.setup();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={vi.fn()} onError={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));

    expect(screen.getByText(/1 documento\(s\)/)).toBeInTheDocument();
  });

  it("confirmar exclusão chama a API e notifica", async () => {
    const user = userEvent.setup();
    mockedDelete.mockResolvedValueOnce(undefined);
    const onChanged = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={onChanged} onError={vi.fn()} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(mockedDelete).toHaveBeenCalledWith("222");
    expect(onChanged).toHaveBeenCalled();
  });

  it("erro na exclusão chama onError com a mensagem da API", async () => {
    const user = userEvent.setup();
    mockedDelete.mockRejectedValueOnce(new RagApiError("Não é possível excluir a collection ativa."));
    const onError = vi.fn();
    render(<CollectionsTable collections={[COLLECTION_INATIVA]} onChanged={vi.fn()} onError={onError} onSuccess={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Excluir" }));
    await user.click(screen.getByRole("button", { name: "Confirmar exclusão" }));

    expect(onError).toHaveBeenCalledWith("Não é possível excluir a collection ativa.");
  });
});
