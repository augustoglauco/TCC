import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CrawlerPanel } from "@/components/admin/CrawlerPanel";
import { CrawlerApiError } from "@/lib/api/crawler";

vi.mock("@/lib/api/crawler", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api/crawler")>("@/lib/api/crawler");
  return { ...actual, runCrawler: vi.fn() };
});
vi.mock("@/lib/api/runtimeSettings", async () => {
  const actual =
    await vi.importActual<typeof import("@/lib/api/runtimeSettings")>("@/lib/api/runtimeSettings");
  return { ...actual, getRuntimeSettings: vi.fn() };
});

import { runCrawler } from "@/lib/api/crawler";
import { getRuntimeSettings } from "@/lib/api/runtimeSettings";

const mockedRunCrawler = vi.mocked(runCrawler);
const mockedGetRuntimeSettings = vi.mocked(getRuntimeSettings);

describe("CrawlerPanel", () => {
  beforeEach(() => {
    mockedRunCrawler.mockReset();
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

  it("dispara o crawl com a URL/profundidade informadas e mostra o resumo", async () => {
    const user = userEvent.setup();
    mockedRunCrawler.mockResolvedValueOnce({
      pages_visited: 3,
      auto_ingested: ["https://exemplo.com/", "https://exemplo.com/a"],
      queued: ["https://exemplo.com/b"],
      errors: [],
    });
    const onFinished = vi.fn();

    render(<CrawlerPanel onFinished={onFinished} />);

    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText(/3 página\(s\) visitada\(s\)/)).toBeInTheDocument();
    expect(mockedRunCrawler).toHaveBeenCalledWith(
      expect.objectContaining({ url: "https://exemplo.com", depth: 1 }),
    );
    await waitFor(() => expect(onFinished).toHaveBeenCalled());
  });

  it("mostra o erro quando o crawler falha", async () => {
    const user = userEvent.setup();
    mockedRunCrawler.mockRejectedValueOnce(new CrawlerApiError("Serviço indisponível."));

    render(<CrawlerPanel onFinished={vi.fn()} />);

    await user.type(screen.getByLabelText("URL semente"), "https://exemplo.com");
    await user.click(screen.getByRole("button", { name: "Rodar crawler" }));

    expect(await screen.findByText("Serviço indisponível.")).toBeInTheDocument();
  });
});
