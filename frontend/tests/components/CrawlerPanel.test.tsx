import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import type { CrawlerStreamCallbacks, CrawlRunPayload } from "@/lib/types/crawler";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, runCrawlerStream: vi.fn() };
});
vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/runtimeSettings")>("@/lib/api/runtimeSettings");
  return { ...actual, getRuntimeSettings: vi.fn() };
});

import { runCrawlerStream } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";

const mockedRunCrawlerStream = vi.mocked(runCrawlerStream);
const mockedGetRuntimeSettings = vi.mocked(getRuntimeSettings);

describe("CrawlerPanel", () => {
  beforeEach(() => {
    mockedRunCrawlerStream.mockReset();
    mockedGetRuntimeSettings.mockReset();
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
      async (_payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
        cbs = callbacks;
        return new Promise<void>(() => {}); // não resolve sozinho — controlado no teste
      },
    );
    const onFinished = vi.fn();

    render(<CrawlerPanel onFinished={onFinished} />);
    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    await waitFor(() => expect(cbs).not.toBeNull());

    act(() => cbs!.onVisiting("https://exemplo.com/"));
    expect(await screen.findByTestId("crawler-live-status")).toHaveTextContent(
      "https://exemplo.com/",
    );

    act(() => cbs!.onIngested("https://exemplo.com/", "vendas"));
    act(() => cbs!.onVisiting("https://exemplo.com/a"));
    act(() => cbs!.onQueued("https://exemplo.com/a", "suporte"));

    const status = screen.getByTestId("crawler-live-status");
    // 2 visitadas, 1 ingerida, 1 na fila, 0 erros
    expect(status).toHaveTextContent("Visitadas");
    expect(status).toHaveTextContent("2");
    expect(status).toHaveTextContent("Ingeridas");
    expect(status).toHaveTextContent("Fila");

    act(() =>
      cbs!.onDone({
        pages_visited: 2,
        auto_ingested: ["https://exemplo.com/"],
        queued: ["https://exemplo.com/a"],
        errors: [],
      }),
    );

    expect(await screen.findByText(/2 página\(s\) visitada\(s\)/)).toBeInTheDocument();
    await waitFor(() => expect(onFinished).toHaveBeenCalled());
  });

  it("avisa possível travamento após silêncio prolongado do servidor", async () => {
    vi.useFakeTimers();
    try {
      let cbs: CrawlerStreamCallbacks | null = null;
      mockedRunCrawlerStream.mockImplementation(
        (_payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
          // Captura síncrona: `cbs` fica disponível assim que o clique dispara.
          cbs = callbacks;
          return new Promise<void>(() => {});
        },
      );

      render(<CrawlerPanel onFinished={vi.fn()} />);
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
      async (_payload: CrawlRunPayload, callbacks: CrawlerStreamCallbacks) => {
        callbacks.onError("Serviço indisponível.");
      },
    );

    render(<CrawlerPanel onFinished={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("URL semente"), {
      target: { value: "https://exemplo.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText("Serviço indisponível.")).toBeInTheDocument();
  });
});
