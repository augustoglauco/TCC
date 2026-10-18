import { renderHook, act } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useCollectionActions } from "@/app/admin/ingestao/useCollectionActions";
import { RagApiError } from "@/lib/api/rag";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/rag", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/rag")>("@/lib/api/rag");
  return {
    ...actual,
    createCollection: vi.fn(),
    activateCollection: vi.fn(),
  };
});

import { activateCollection, createCollection } from "@/lib/api/rag";

const mockedCreateCollection = vi.mocked(createCollection);
const mockedActivateCollection = vi.mocked(activateCollection);

function colecao(over: Partial<RagCollection> = {}): RagCollection {
  return {
    id: "col-1",
    name: "docs_chat",
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
    document_count: 0,
    created_at: new Date().toISOString(),
    ...over,
  };
}

function renderActions(overrides: Partial<Parameters<typeof useCollectionActions>[0]> = {}) {
  const onColecoesMudaram = vi.fn().mockResolvedValue([colecao()]);
  const onCollectionIdChange = vi.fn();
  const onError = vi.fn();

  const { result } = renderHook(() =>
    useCollectionActions({
      onColecoesMudaram,
      onCollectionIdChange,
      onError,
      ...overrides,
    }),
  );

  return { result, onColecoesMudaram, onCollectionIdChange, onError };
}

describe("useCollectionActions — estado inicial", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token",
    });
  });

  it("começa com criandoCollection=false e modalCriarAberto=false", () => {
    const { result } = renderActions();
    expect(result.current.criandoCollection).toBe(false);
    expect(result.current.modalCriarAberto).toBe(false);
  });
});

describe("useCollectionActions — criarCollectionRapida", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token",
    });
  });

  it("cria collection chat com nome 'docs_chat' e seleciona o id retornado", async () => {
    const novaCol = colecao({ id: "col-new", name: "docs_chat", purpose: "chat" });
    mockedCreateCollection.mockResolvedValueOnce(novaCol);
    mockedActivateCollection.mockResolvedValueOnce(undefined);

    const { result, onColecoesMudaram, onCollectionIdChange, onError } = renderActions();

    await act(async () => {
      await result.current.criarCollectionRapida("chat");
    });

    expect(mockedCreateCollection).toHaveBeenCalledWith(
      "mock-token",
      expect.objectContaining({ name: "docs_chat", purpose: "chat" }),
    );
    expect(mockedActivateCollection).toHaveBeenCalledWith("mock-token", "col-new");
    expect(onColecoesMudaram).toHaveBeenCalled();
    expect(onCollectionIdChange).toHaveBeenCalledWith("col-new");
    expect(onError).toHaveBeenCalledWith("");
  });

  it("cria collection mcp_b2b com nome 'docs_mcp_b2b'", async () => {
    const novaCol = colecao({ id: "col-b2b", name: "docs_mcp_b2b", purpose: "mcp_b2b" });
    mockedCreateCollection.mockResolvedValueOnce(novaCol);
    mockedActivateCollection.mockResolvedValueOnce(undefined);

    const { result, onCollectionIdChange } = renderActions();

    await act(async () => {
      await result.current.criarCollectionRapida("mcp_b2b");
    });

    expect(mockedCreateCollection).toHaveBeenCalledWith(
      "mock-token",
      expect.objectContaining({ name: "docs_mcp_b2b", purpose: "mcp_b2b" }),
    );
    expect(onCollectionIdChange).toHaveBeenCalledWith("col-b2b");
  });

  it("cria collection admin com nome 'docs_admin'", async () => {
    const novaCol = colecao({ id: "col-adm", name: "docs_admin", purpose: "admin" });
    mockedCreateCollection.mockResolvedValueOnce(novaCol);
    mockedActivateCollection.mockResolvedValueOnce(undefined);

    const { result, onCollectionIdChange } = renderActions();

    await act(async () => {
      await result.current.criarCollectionRapida("admin");
    });

    expect(mockedCreateCollection).toHaveBeenCalledWith(
      "mock-token",
      expect.objectContaining({ name: "docs_admin", purpose: "admin" }),
    );
    expect(onCollectionIdChange).toHaveBeenCalledWith("col-adm");
  });

  it("não faz nada quando token é null", async () => {
    useAuthStore.setState({ user: null, token: null });
    const { result, onColecoesMudaram, onCollectionIdChange } = renderActions();

    await act(async () => {
      await result.current.criarCollectionRapida("chat");
    });

    expect(mockedCreateCollection).not.toHaveBeenCalled();
    expect(onColecoesMudaram).not.toHaveBeenCalled();
    expect(onCollectionIdChange).not.toHaveBeenCalled();
  });

  it("ativa criandoCollection durante a criação e restaura ao terminar", async () => {
    let resolveCreate!: (v: RagCollection) => void;
    mockedCreateCollection.mockReturnValueOnce(
      new Promise<RagCollection>((res) => {
        resolveCreate = res;
      }),
    );
    mockedActivateCollection.mockResolvedValueOnce(undefined);

    const { result, onColecoesMudaram } = renderActions({
      onColecoesMudaram: vi.fn().mockResolvedValue([]),
    });

    act(() => {
      void result.current.criarCollectionRapida("chat");
    });

    expect(result.current.criandoCollection).toBe(true);

    await act(async () => {
      resolveCreate(colecao({ id: "col-x" }));
      await onColecoesMudaram();
    });

    expect(result.current.criandoCollection).toBe(false);
  });

  it("fallback: quando createCollection falha mas a collection já existe, seleciona a existente", async () => {
    const colExistente = colecao({ id: "col-existente", name: "docs_chat", purpose: "chat" });
    mockedCreateCollection.mockRejectedValueOnce(new RagApiError("já existe", 409));

    const onColecoesMudaram = vi.fn().mockResolvedValue([colExistente]);
    const onCollectionIdChange = vi.fn();
    const onError = vi.fn();

    const { result } = renderHook(() =>
      useCollectionActions({ onColecoesMudaram, onCollectionIdChange, onError }),
    );

    await act(async () => {
      await result.current.criarCollectionRapida("chat");
    });

    expect(onCollectionIdChange).toHaveBeenCalledWith("col-existente");
    // onError chamado com "" para limpar erro anterior
    expect(onError).toHaveBeenLastCalledWith("");
    expect(onColecoesMudaram).toHaveBeenCalled();
  });

  it("fallback: quando createCollection falha e a collection não existe, propaga o erro", async () => {
    mockedCreateCollection.mockRejectedValueOnce(
      new RagApiError("Serviço indisponível", 503),
    );

    const { result, onCollectionIdChange, onError } = renderActions({
      onColecoesMudaram: vi.fn().mockResolvedValue([]),
    });

    await act(async () => {
      await result.current.criarCollectionRapida("chat");
    });

    expect(onCollectionIdChange).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith("Serviço indisponível");
  });

  it("continua mesmo quando activateCollection falha (não impeditivo)", async () => {
    const novaCol = colecao({ id: "col-ok" });
    mockedCreateCollection.mockResolvedValueOnce(novaCol);
    mockedActivateCollection.mockRejectedValueOnce(new Error("ativação falhou"));

    const { result, onCollectionIdChange, onError } = renderActions();

    await act(async () => {
      await result.current.criarCollectionRapida("chat");
    });

    expect(onCollectionIdChange).toHaveBeenCalledWith("col-ok");
    // onError não deve ter sido chamado com mensagem de erro
    expect(onError).not.toHaveBeenCalledWith(expect.stringContaining("ativação"));
  });
});

describe("useCollectionActions — handleSelectCollectionChange", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token",
    });
  });

  it("valor '__create_mcp_b2b__' dispara criarCollectionRapida('mcp_b2b')",
    async () => {
      const novaCol = colecao({ id: "col-x", purpose: "mcp_b2b" });
      mockedCreateCollection.mockResolvedValueOnce(novaCol);
      mockedActivateCollection.mockResolvedValueOnce(undefined);

      const { result, onCollectionIdChange } = renderActions();

      await act(async () => {
        result.current.handleSelectCollectionChange("__create_mcp_b2b__");
        await Promise.resolve();
      });

      expect(mockedCreateCollection).toHaveBeenCalledWith(
        "mock-token",
        expect.objectContaining({ purpose: "mcp_b2b" }),
      );
      expect(onCollectionIdChange).toHaveBeenCalledWith("col-x");
    },
  );

  it("valor '__create_admin__' dispara criarCollectionRapida('admin')",
    async () => {
      const novaCol = colecao({ id: "col-x", purpose: "admin" });
      mockedCreateCollection.mockResolvedValueOnce(novaCol);
      mockedActivateCollection.mockResolvedValueOnce(undefined);

      const { result, onCollectionIdChange } = renderActions();

      await act(async () => {
        result.current.handleSelectCollectionChange("__create_admin__");
        await Promise.resolve();
      });

      expect(mockedCreateCollection).toHaveBeenCalledWith(
        "mock-token",
        expect.objectContaining({ purpose: "admin" }),
      );
      expect(onCollectionIdChange).toHaveBeenCalledWith("col-x");
    },
  );

  it("valor '__create_chat__' dispara criarCollectionRapida('chat')",
    async () => {
      const novaCol = colecao({ id: "col-x", purpose: "chat" });
      mockedCreateCollection.mockResolvedValueOnce(novaCol);
      mockedActivateCollection.mockResolvedValueOnce(undefined);

      const { result, onCollectionIdChange } = renderActions();

      await act(async () => {
        result.current.handleSelectCollectionChange("__create_chat__");
        await Promise.resolve();
      });

      expect(mockedCreateCollection).toHaveBeenCalledWith(
        "mock-token",
        expect.objectContaining({ purpose: "chat" }),
      );
      expect(onCollectionIdChange).toHaveBeenCalledWith("col-x");
    },
  );

  it("valor '__open_modal__' abre o modal de criação", () => {
    const { result } = renderActions();

    act(() => {
      result.current.handleSelectCollectionChange("__open_modal__");
    });

    expect(result.current.modalCriarAberto).toBe(true);
  });

  it("valor de id normal chama onCollectionIdChange diretamente", () => {
    const { result, onCollectionIdChange } = renderActions();

    act(() => {
      result.current.handleSelectCollectionChange("col-42");
    });

    expect(onCollectionIdChange).toHaveBeenCalledWith("col-42");
    expect(mockedCreateCollection).not.toHaveBeenCalled();
  });
});
