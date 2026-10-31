import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerReviewQueue } from "@/components/admin/CrawlerReviewQueue";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { PendingPage } from "@/lib/types/crawler";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return {
    ...actual,
    listPendingPages: vi.fn(),
    approvePendingPage: vi.fn(),
    rejectPendingPage: vi.fn(),
  };
});

import { approvePendingPage, listPendingPages, rejectPendingPage } from "@/lib/api/crawler";

const mockedList = vi.mocked(listPendingPages);
const mockedApprove = vi.mocked(approvePendingPage);
const mockedReject = vi.mocked(rejectPendingPage);

const COLECAO_CHAT: RagCollection = {
  id: "col-chat",
  name: "docs_chat",
  embedding_model: "m",
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
};
const COLECAO_GERAL: RagCollection = {
  ...COLECAO_CHAT,
  id: "col-geral",
  name: "DocsGeral",
  is_active: false,
};

const PAGINA: PendingPage = {
  id: "pagina-1",
  url: "https://exemplo.com/ambiguo",
  text_snippet: "trecho do conteúdo",
  domain_proposed: "vendas",
  confidence: 0.42,
  collection_id: null,
  collection_name: null,
  created_at: new Date().toISOString(),
};

describe("CrawlerReviewQueue", () => {
  beforeEach(() => {
    mockedList.mockReset();
    mockedApprove.mockReset();
    mockedReject.mockReset();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
  });

  it("mostra a mensagem de fila vazia quando não há páginas pendentes", async () => {
    mockedList.mockResolvedValueOnce([]);

    render(<CrawlerReviewQueue reloadKey={0} collections={[COLECAO_CHAT, COLECAO_GERAL]} />);

    expect(await screen.findByText("Nenhuma página pendente de revisão.")).toBeInTheDocument();
  });

  it("aprova a página com o domain selecionado e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedApprove.mockResolvedValueOnce({ url: PAGINA.url, domain: "suporte", chunks: 1 });

    render(<CrawlerReviewQueue reloadKey={0} collections={[COLECAO_CHAT, COLECAO_GERAL]} />);

    await screen.findByText(PAGINA.url);
    await user.selectOptions(screen.getByLabelText(`Domínio de ${PAGINA.url}`), "suporte");
    await user.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(mockedApprove).toHaveBeenCalledWith("mock-token-1", PAGINA.id, { domain: "suporte" });
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });

  it("rejeita a página e remove da lista", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedReject.mockResolvedValueOnce(undefined);

    render(<CrawlerReviewQueue reloadKey={0} collections={[COLECAO_CHAT, COLECAO_GERAL]} />);

    await screen.findByText(PAGINA.url);
    await user.click(screen.getByRole("button", { name: "Rejeitar" }));

    expect(mockedReject).toHaveBeenCalledWith("mock-token-1", PAGINA.id);
    expect(screen.queryByText(PAGINA.url)).not.toBeInTheDocument();
  });

  it("aprova na collection escolhida na linha", async () => {
    const user = userEvent.setup();
    mockedList.mockResolvedValueOnce([PAGINA]);
    mockedApprove.mockResolvedValueOnce({ url: PAGINA.url, domain: "vendas", chunks: 1 });

    render(<CrawlerReviewQueue reloadKey={0} collections={[COLECAO_CHAT, COLECAO_GERAL]} />);
    await screen.findByText(PAGINA.url);
    await user.selectOptions(screen.getByLabelText(`Collection de ${PAGINA.url}`), "col-geral");
    await user.click(screen.getByRole("button", { name: "Aprovar" }));

    expect(mockedApprove).toHaveBeenCalledWith("mock-token-1", PAGINA.id, {
      domain: "vendas",
      collection_id: "col-geral",
    });
  });

  it("pré-seleciona a collection gravada na página pendente", async () => {
    mockedList.mockResolvedValueOnce([
      { ...PAGINA, collection_id: "col-geral", collection_name: "DocsGeral" },
    ]);

    render(<CrawlerReviewQueue reloadKey={0} collections={[COLECAO_CHAT, COLECAO_GERAL]} />);

    const select = await screen.findByLabelText(`Collection de ${PAGINA.url}`);
    expect(select).toHaveValue("col-geral");
  });
});
