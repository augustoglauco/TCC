import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CollectionOptionCard } from "@/components/admin/playground/CollectionOptionCard";
import type { RagCollection } from "@/lib/types/rag";

const MOCK_COLLECTION: RagCollection = {
  id: "col-123",
  name: "collection_vendas",
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
  payload_indexes: [{ field: "domain", schema_type: "keyword" }],
  is_active: true,
  purpose: "chat",
  document_count: 7,
  created_at: "2026-09-20T10:00:00Z",
};

describe("CollectionOptionCard", () => {
  it("renderiza o card com o nome e status da collection", () => {
    render(
      <CollectionOptionCard
        collection={MOCK_COLLECTION}
        isSelected={false}
        onToggle={vi.fn()}
      />,
    );

    expect(screen.getByText("collection_vendas")).toBeInTheDocument();
    expect(screen.getByText("Ativa")).toBeInTheDocument();
  });

  it("chama onToggle ao clicar no checkbox", async () => {
    const user = userEvent.setup();
    const onToggle = vi.fn();
    render(
      <CollectionOptionCard
        collection={MOCK_COLLECTION}
        isSelected={false}
        onToggle={onToggle}
      />,
    );

    const checkbox = screen.getByLabelText("collection_vendas");
    await user.click(checkbox);

    expect(onToggle).toHaveBeenCalledWith("col-123");
  });

  it("exibe bubble com todos os parâmetros e quantidade de arquivos no hover e oculta no mouseLeave", async () => {
    render(
      <CollectionOptionCard
        collection={MOCK_COLLECTION}
        isSelected={false}
        onToggle={vi.fn()}
      />,
    );

    const card = screen.getByText("collection_vendas").closest("label");
    expect(card).not.toBeNull();

    // Inicialmente a bubble não está no documento
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    // Dispara mouseEnter
    fireEvent.mouseEnter(card!);

    // Bubble deve surgir com as informações detalhadas
    const bubble = screen.getByRole("tooltip");
    expect(bubble).toBeInTheDocument();

    // Quantidade de arquivos
    expect(screen.getByText(/Arquivos indexados:/i)).toBeInTheDocument();
    expect(screen.getByText(/7 documentos/i)).toBeInTheDocument();

    // Parâmetros técnicos
    expect(screen.getByText("paraphrase-multilingual-MiniLM-L12-v2")).toBeInTheDocument();
    expect(screen.getByText("384")).toBeInTheDocument();
    expect(screen.getByText(/cosine/i)).toBeInTheDocument();
    expect(screen.getByText("800 tokens")).toBeInTheDocument();
    expect(screen.getByText("100 tokens")).toBeInTheDocument();
    expect(screen.getByText("16 / 100")).toBeInTheDocument();
    expect(screen.getByText("Em RAM")).toBeInTheDocument();

    // Dispara mouseLeave
    fireEvent.mouseLeave(card!);

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });
});
