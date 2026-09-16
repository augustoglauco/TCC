import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CollectionFormModal } from "@/components/admin/CollectionFormModal";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, createCollection: vi.fn() };
});

import { createCollection, RagApiError } from "@/lib/api/rag";

const mockedCreate = vi.mocked(createCollection);

const COLLECTION_CRIADA: RagCollection = {
  id: "1",
  name: "nova",
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
  is_active: false,
  document_count: 0,
  created_at: new Date().toISOString(),
};

describe("CollectionFormModal", () => {
  beforeEach(() => {
    mockedCreate.mockReset();
  });

  it("preenche nome e envia — chama createCollection com o payload esperado", async () => {
    const user = userEvent.setup();
    mockedCreate.mockResolvedValueOnce(COLLECTION_CRIADA);
    const onCreated = vi.fn();

    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={onCreated} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    await user.click(screen.getByRole("button", { name: "Criar collection" }));

    expect(mockedCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: "nova", embedding_model: "paraphrase-multilingual-MiniLM-L12-v2" }),
    );
    expect(onCreated).toHaveBeenCalledWith(COLLECTION_CRIADA);
  });

  it("selecionar 'Outro' revela campo de texto livre para o modelo", async () => {
    const user = userEvent.setup();
    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.selectOptions(screen.getAllByRole("combobox")[0], "__custom__");

    expect(screen.getByLabelText("Nome do modelo")).toBeInTheDocument();
  });

  it("chunk_size menor ou igual ao overlap desabilita o envio e mostra aviso", async () => {
    const user = userEvent.setup();
    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    const chunkSizeInput = screen.getByLabelText(/Chunk size/);
    await user.clear(chunkSizeInput);
    await user.type(chunkSizeInput, "50");

    expect(screen.getByText(/deve ser maior que o overlap/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Criar collection" })).toBeDisabled();
  });

  it("exibe erro da API quando a criação falha (ex.: nome duplicado)", async () => {
    const user = userEvent.setup();
    mockedCreate.mockRejectedValueOnce(new RagApiError("Já existe uma collection chamada 'nova'."));

    render(<CollectionFormModal open onOpenChange={vi.fn()} onCreated={vi.fn()} />);

    await user.type(screen.getByLabelText("Nome"), "nova");
    await user.click(screen.getByRole("button", { name: "Criar collection" }));

    expect(await screen.findByText("Já existe uma collection chamada 'nova'.")).toBeInTheDocument();
  });
});
