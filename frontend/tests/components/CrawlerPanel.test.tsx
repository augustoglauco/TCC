import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { CrawlerStreamCallbacks, CrawlRunPayload } from "@/lib/types/crawler";
import type { RagCollection } from "@/lib/types/rag";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, runCrawlerStream: vi.fn() };
});
// Alias do tipo do módulo: `vi.importActual<typeof import("…")>("…")` em uma
// chamada quebrada em várias linhas é TypeScript válido, mas o parser TSX do
// tree-sitter (usado pelo extrator do graphify) falha no argumento após o
// argumento de tipo, e o arquivo inteiro deixa de entrar no grafo
// (`graphify-out/`). Com o alias a chamada cabe em uma linha.
type RuntimeSettingsModule = typeof import("@/lib/api/runtimeSettings");

vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual = await vi.importActual<RuntimeSettingsModule>("@/lib/api/runtimeSettings");
  return { ...actual, getRuntimeSettings: vi.fn() };
});

import { runCrawlerStream } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";

const mockedRunCrawlerStream = vi.mocked(runCrawlerStream);
const mockedGetRuntimeSettings = vi.mocked(getRuntimeSettings);

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

const PROPS_BASE = {
  collections: [COLECAO_CHAT, COLECAO_GERAL],
  onColecoesMudaram: vi.fn().mockResolvedValue([COLECAO_CHAT, COLECAO_GERAL]),
};

describe("CrawlerPanel", () => {
  beforeEach(() => {
    mockedRunCrawlerStream.mockReset();
    mockedGetRuntimeSettings.mockReset();
    useAuthStore.setState({
      user: { id: 1, nome: "Admin Teste", email: "admin@empresa.com", perfil: "Admin" },
      token: "mock-token-1",
    });
    mockedGetRuntimeSettings.mockResolvedValue({
      local_llm_temperature: null,
      local_llm_timeout_s: 30,
      external_llm_timeout_s: 30,
      rag_search_domain_fallback: false,
      crawler_max_pages_default: 20,
      crawler_confidence_threshold: 0.7,
    });
  });

  it("mostra progresso ao vivo (URL atual + contadores) e o resumo final", async () => {
    const user = userEvent.setup();
    // Captura os callbacks para dirigir o "stream" manualmente no teste.
    let cbs: CrawlerStreamCallbacks | null = null;
    mockedRunCrawlerStream.mockImplementation(
      async (_token: string, _payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
        cbs = callbacks;
        return new Promise<void>(() => {}); // não resolve sozinho — controlado no teste
      },
    );
    const onFinished = vi.fn();

    render(<CrawlerPanel {...PROPS_BASE} onFinished={onFinished} />);
    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    await waitFor(() => expect(cbs).not.toBeNull());

    act(() => cbs!.onVisiting("https://exemplo.com/"));
    expect(await screen.findByTestId("crawler-live-status")).toHaveTextContent(
      "https://exemplo.com/",
    );

    act(() => cbs!.onQueued("https://exemplo.com/", "vendas"));
    act(() => cbs!.onVisiting("https://exemplo.com/a"));
    act(() => cbs!.onQueued("https://exemplo.com/a", "suporte"));

    const status = screen.getByTestId("crawler-live-status");
    // 2 visitadas, 2 na fila, 0 erros
    expect(status).toHaveTextContent("Visitadas");
    expect(status).toHaveTextContent("2");
    expect(status).not.toHaveTextContent("Ingeridas");
    expect(status).toHaveTextContent("Fila");

    act(() =>
      cbs!.onDone({
        pages_visited: 2,
        queued: ["https://exemplo.com/", "https://exemplo.com/a"],
        errors: [],
      }),
    );

    expect(await screen.findByText(/2 página\(s\) visitada\(s\)/)).toHaveTextContent(
      "2 na fila de revisão",
    );
    await waitFor(() => expect(onFinished).toHaveBeenCalled());
  });

  it("avisa possível travamento após silêncio prolongado do servidor", async () => {
    vi.useFakeTimers();
    try {
      let cbs: CrawlerStreamCallbacks | null = null;
      mockedRunCrawlerStream.mockImplementation(
        (_token: string, _payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
          // Captura síncrona: `cbs` fica disponível assim que o clique dispara.
          cbs = callbacks;
          return new Promise<void>(() => {});
        },
      );

      render(<CrawlerPanel {...PROPS_BASE} onFinished={vi.fn()} />);
      fireEvent.change(screen.getByLabelText("URL semente"), {
        target: { value: "https://exemplo.com" },
      });
      fireEvent.click(screen.getByRole("button", { name: "Rodar crawler" }));

      // `cbs` já foi capturado de forma síncrona no clique; sinaliza uma
      // atividade e então avança o relógio além do limiar (20s) sem novos
      // eventos — a interval do heartbeat (criada com fake timers ativos)
      // deve marcar o travamento.
      expect(cbs).not.toBeNull();
      act(() => cbs!.onVisiting("https://exemplo.com/"));
      act(() => vi.advanceTimersByTime(21_000));

      expect(screen.getByTestId("crawler-stall-warning")).toBeInTheDocument();
      expect(screen.getByTestId("crawler-stall-warning")).toHaveTextContent(/travad/i);
    } finally {
      vi.useRealTimers();
    }
  });

  it("mostra o erro quando o stream falha", async () => {
    mockedRunCrawlerStream.mockImplementation(
      async (_token: string, _payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
        callbacks.onError("Serviço indisponível.");
      },
    );

    render(<CrawlerPanel {...PROPS_BASE} onFinished={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("URL semente"), {
      target: { value: "https://exemplo.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText("Serviço indisponível.")).toBeInTheDocument();
  });

  it("envia a collection escolhida no payload do crawl, sem modo automático", async () => {
    const user = userEvent.setup();
    mockedRunCrawlerStream.mockResolvedValue(undefined);

    render(<CrawlerPanel {...PROPS_BASE} onFinished={vi.fn()} />);
    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.selectOptions(screen.getByLabelText("Collection destino"), "col-geral");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    await waitFor(() => expect(mockedRunCrawlerStream).toHaveBeenCalled());
    const payload = mockedRunCrawlerStream.mock.calls[0][1];
    expect(payload).toMatchObject({ collection_id: "col-geral" });
    expect(payload).not.toHaveProperty("review");
    expect(screen.queryByLabelText(/Revisar antes de ingerir/)).not.toBeInTheDocument();
  });

  it("sem escolha, usa a collection ativa no chat", async () => {
    const user = userEvent.setup();
    mockedRunCrawlerStream.mockResolvedValue(undefined);

    render(<CrawlerPanel {...PROPS_BASE} onFinished={vi.fn()} />);
    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    await waitFor(() => expect(mockedRunCrawlerStream).toHaveBeenCalled());
    expect(mockedRunCrawlerStream.mock.calls[0][1]).toMatchObject({ collection_id: "col-chat" });
  });
});
