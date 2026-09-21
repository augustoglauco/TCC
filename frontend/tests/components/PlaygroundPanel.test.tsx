import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return { ...actual, runPlaygroundSearch: vi.fn() };
});

import { RagApiError, runPlaygroundSearch } from "@/lib/api/rag";

const mockedRunSearch = vi.mocked(runPlaygroundSearch);

function collection(overrides: Partial<RagCollection>): RagCollection {
  return {
    id: "1",
    name: "docs_texto",
    embedding_model: "modelo",
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
    document_count: 0,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const COLLECTION_A = collection({ id: "a", name: "collection-a" });
const COLLECTION_B = collection({ id: "b", name: "collection-b", is_active: false });

describe("PlaygroundPanel", () => {
  beforeEach(() => {
    mockedRunSearch.mockReset();
  });

  it("botão comparar fica desabilitado sem pergunta ou sem collection marcada", () => {
    render(<PlaygroundPanel collections={[COLLECTION_A, COLLECTION_B]} />);

    expect(screen.getByRole("button", { name: "Comparar" })).toBeDisabled();
  });

  it("roda a busca e renderiza um card por collection, com resultado e erro isolados", async () => {
    const user = userEvent.setup();
    mockedRunSearch.mockResolvedValueOnce({
      items: [
        {
          collection_id: "a",
          collection_name: "collection-a",
          latency_ms: 12.3,
          results: [{ content: "conteúdo de teste", source: "a.txt", score: 0.8 }],
        },
        {
          collection_id: "b",
          collection_name: "collection-b",
          error: "Serviço de RAG temporariamente indisponível.",
        },
      ],
    });

    render(<PlaygroundPanel collections={[COLLECTION_A, COLLECTION_B]} />);

    await user.type(screen.getByLabelText("Pergunta de teste"), "qual a garantia?");
    await user.click(screen.getByLabelText("collection-a"));
    await user.click(screen.getByLabelText("collection-b"));
    await user.click(screen.getByRole("button", { name: "Comparar" }));

    expect(mockedRunSearch).toHaveBeenCalledWith({
      query: "qual a garantia?",
      domain: "vendas",
      collection_ids: ["a", "b"],
    });
    expect(await screen.findByText("conteúdo de teste")).toBeInTheDocument();
    expect(screen.getByText("Serviço de RAG temporariamente indisponível.")).toBeInTheDocument();
  });

  it("exibe erro geral quando a chamada falha por inteiro", async () => {
    const user = userEvent.setup();
    mockedRunSearch.mockRejectedValueOnce(new RagApiError("Não foi possível rodar a busca."));

    render(<PlaygroundPanel collections={[COLLECTION_A]} />);

    await user.type(screen.getByLabelText("Pergunta de teste"), "pergunta");
    await user.click(screen.getByLabelText("collection-a"));
    await user.click(screen.getByRole("button", { name: "Comparar" }));

    expect(await screen.findByText("Não foi possível rodar a busca.")).toBeInTheDocument();
  });
});
