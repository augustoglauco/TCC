import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlaygroundPanel } from "@/components/admin/playground/PlaygroundPanel";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
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
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
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

    expect(mockedRunSearch).toHaveBeenCalledWith("mock-token-1", {
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

  it("permite selecionar e desmarcar todas as collections com os botões rápidos", async () => {
    const user = userEvent.setup();
    render(<PlaygroundPanel collections={[COLLECTION_A, COLLECTION_B]} />);

    const checkboxA = screen.getByLabelText("collection-a") as HTMLInputElement;
    const checkboxB = screen.getByLabelText("collection-b") as HTMLInputElement;

    expect(checkboxA.checked).toBe(false);
    expect(checkboxB.checked).toBe(false);

    // Clica em 'Selecionar todas'
    await user.click(screen.getByRole("button", { name: "Selecionar todas" }));
    expect(checkboxA.checked).toBe(true);
    expect(checkboxB.checked).toBe(true);

    // Clica em 'Limpar seleção'
    await user.click(screen.getByRole("button", { name: "Limpar seleção" }));
    expect(checkboxA.checked).toBe(false);
    expect(checkboxB.checked).toBe(false);
  });

  it("permite limpar os resultados após uma busca", async () => {
    const user = userEvent.setup();
    mockedRunSearch.mockResolvedValueOnce({
      items: [
        {
          collection_id: "a",
          collection_name: "collection-a",
          latency_ms: 25,
          results: [{ content: "resultado teste limpeza", source: "doc.txt", score: 0.9 }],
        },
      ],
    });

    render(<PlaygroundPanel collections={[COLLECTION_A]} />);

    await user.type(screen.getByLabelText("Pergunta de teste"), "teste limpeza");
    await user.click(screen.getByLabelText("collection-a"));
    await user.click(screen.getByRole("button", { name: "Comparar" }));

    expect(await screen.findByText("resultado teste limpeza")).toBeInTheDocument();

    // Clica em Limpar resultados
    await user.click(screen.getByRole("button", { name: "Limpar resultados" }));
    expect(screen.queryByText("resultado teste limpeza")).not.toBeInTheDocument();
    expect(screen.getByText("Pronto para comparar o comportamento do RAG")).toBeInTheDocument();
  });

  it("abre e fecha o manual de uso do Playground", async () => {
    const user = userEvent.setup();
    render(<PlaygroundPanel collections={[COLLECTION_A]} />);

    const btnManual = screen.getByRole("button", { name: /Como usar o Playground/i });
    expect(btnManual).toBeInTheDocument();

    // Clica para abrir o modal do manual
    await user.click(btnManual);

    expect(screen.getByText("📖 Manual de Uso do Playground RAG")).toBeInTheDocument();
    expect(screen.getByText(/O que é o Playground\?/i)).toBeInTheDocument();
    expect(screen.getByText(/Score de Similaridade/i)).toBeInTheDocument();

    // Fecha o modal
    const btnFechar = screen.getByRole("button", { name: /Entendi, fechar manual/i });
    await user.click(btnFechar);

    expect(screen.queryByText("📖 Manual de Uso do Playground RAG")).not.toBeInTheDocument();
  });

  it("filtra collections por purpose garantindo comparação apenas entre mesmo canal", async () => {
    const user = userEvent.setup();
    const colChat = collection({ id: "c1", name: "col-chat", purpose: "chat" });
    const colB2b = collection({ id: "c2", name: "col-b2b", purpose: "mcp_b2b" });

    render(<PlaygroundPanel collections={[colChat, colB2b]} />);

    // Por padrão exibe 'Chat (Público)'
    expect(screen.getByLabelText("col-chat")).toBeInTheDocument();
    expect(screen.queryByLabelText("col-b2b")).not.toBeInTheDocument();

    // Alterna para 'MCP B2B (Parceiros)'
    await user.click(screen.getByRole("button", { name: /MCP B2B/i }));

    expect(screen.queryByLabelText("col-chat")).not.toBeInTheDocument();
    expect(screen.getByLabelText("col-b2b")).toBeInTheDocument();
  });
});
