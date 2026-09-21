import { afterEach, describe, expect, it, vi } from "vitest";

import { runCrawlerStream } from "@/lib/api/crawler";
import type { CrawlerStreamCallbacks } from "@/lib/types/crawler";

function sseStream(blocks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < blocks.length) {
        controller.enqueue(encoder.encode(blocks[i]));
        i += 1;
      } else {
        controller.close();
      }
    },
  });
}

function mockFetchOnce(body: ReadableStream<Uint8Array> | null, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok,
      status,
      body,
      json: async () => ({}),
    } as Response),
  );
}

function fakeCallbacks(): CrawlerStreamCallbacks {
  return {
    onVisiting: vi.fn(),
    onIngested: vi.fn(),
    onQueued: vi.fn(),
    onPageError: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn(),
  };
}

describe("runCrawlerStream", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("dispara os callbacks na ordem dos eventos e monta o done", async () => {
    mockFetchOnce(
      sseStream([
        'event: visitando\ndata: {"url":"https://exemplo.com/"}\n\n',
        'event: ingerida\ndata: {"url":"https://exemplo.com/","domain":"vendas"}\n\n',
        'event: visitando\ndata: {"url":"https://exemplo.com/a"}\n\n',
        'event: enfileirada\ndata: {"url":"https://exemplo.com/a","domain":"suporte"}\n\n',
        'event: done\ndata: {"pages_visited":2,"auto_ingested":["https://exemplo.com/"],"queued":["https://exemplo.com/a"],"errors":[]}\n\n',
      ]),
    );

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 1 }, cbs);

    expect(cbs.onVisiting).toHaveBeenNthCalledWith(1, "https://exemplo.com/");
    expect(cbs.onIngested).toHaveBeenCalledWith("https://exemplo.com/", "vendas");
    expect(cbs.onVisiting).toHaveBeenNthCalledWith(2, "https://exemplo.com/a");
    expect(cbs.onQueued).toHaveBeenCalledWith("https://exemplo.com/a", "suporte");
    expect(cbs.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ pages_visited: 2, errors: [] }),
    );
    expect(cbs.onError).not.toHaveBeenCalled();
  });

  it("mapeia o evento erro (por página) para onPageError", async () => {
    mockFetchOnce(
      sseStream([
        'event: visitando\ndata: {"url":"https://exemplo.com/x"}\n\n',
        'event: erro\ndata: {"url":"https://exemplo.com/x"}\n\n',
        'event: done\ndata: {"pages_visited":0,"auto_ingested":[],"queued":[],"errors":["https://exemplo.com/x"]}\n\n',
      ]),
    );

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 0 }, cbs);

    expect(cbs.onPageError).toHaveBeenCalledWith("https://exemplo.com/x");
    expect(cbs.onDone).toHaveBeenCalled();
  });

  it("chama onError no evento error global", async () => {
    mockFetchOnce(sseStream(['event: error\ndata: {"detail":"Falha no crawl: boom"}\n\n']));

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 0 }, cbs);

    expect(cbs.onError).toHaveBeenCalledWith("Falha no crawl: boom");
    expect(cbs.onDone).not.toHaveBeenCalled();
  });

  it("chama onError quando o fetch de rede falha", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 0 }, cbs);

    expect(cbs.onError).toHaveBeenCalledWith(
      "Não foi possível conectar ao servidor. Verifique sua conexão.",
    );
  });

  it("chama onError quando a resposta HTTP não é 2xx", async () => {
    mockFetchOnce(null, false, 503);

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 0 }, cbs);

    expect(cbs.onError).toHaveBeenCalledWith(
      "Serviço de RAG temporariamente indisponível. Tente novamente.",
    );
  });

  it("chama onError se o stream terminar sem done", async () => {
    mockFetchOnce(sseStream(['event: visitando\ndata: {"url":"https://exemplo.com/"}\n\n']));

    const cbs = fakeCallbacks();
    await runCrawlerStream({ url: "https://exemplo.com", depth: 0 }, cbs);

    expect(cbs.onVisiting).toHaveBeenCalled();
    expect(cbs.onError).toHaveBeenCalledWith(
      "Resposta incompleta do servidor (crawl pode ter sido interrompido).",
    );
  });
});
