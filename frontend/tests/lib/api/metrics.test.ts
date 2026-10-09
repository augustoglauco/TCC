import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchAiUsageMetrics } from "@/lib/api/metrics";

const RELATORIO_VAZIO = {
  period: "7d",
  atendimento: { chats_encerrados: 0 },
  totais: {
    chamadas: 0,
    tokens_entrada: null,
    tokens_saida: null,
    custo_usd: null,
    chamadas_sem_custo_medido: 0,
  },
  por_origem: [],
  por_ambiente: [],
  por_modelo: [],
  por_operacao: [],
  diario: [],
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("fetchAiUsageMetrics", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requisita o caminho /api/admin/metrics/ai-usage", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(RELATORIO_VAZIO));
    vi.stubGlobal("fetch", mockFetch);

    await fetchAiUsageMetrics("mock-token", { period: "7d" });

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/admin/metrics/ai-usage");
  });

  it("mapeia startDate/endDate para start_date/end_date na query string", async () => {
    // Regressão (revisão final de ponta a ponta, 2026-10-09): nenhum
    // teste cobria isto além dos testes de página, que espionam a função
    // inteira em vez de checar a URL — um typo em qualquer um dos dois
    // nomes de parâmetro ficaria invisível para a CI.
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(RELATORIO_VAZIO));
    vi.stubGlobal("fetch", mockFetch);

    await fetchAiUsageMetrics("mock-token", {
      period: "custom",
      startDate: "2026-03-10",
      endDate: "2026-03-12",
    });

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url);
    expect(parsed.searchParams.get("start_date")).toBe("2026-03-10");
    expect(parsed.searchParams.get("end_date")).toBe("2026-03-12");
    expect(parsed.searchParams.get("period")).toBe("custom");
  });

  it("não manda start_date/end_date quando startDate/endDate não são passados", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(RELATORIO_VAZIO));
    vi.stubGlobal("fetch", mockFetch);

    await fetchAiUsageMetrics("mock-token", { period: "7d" });

    const [url] = mockFetch.mock.calls[0] as [string, RequestInit];
    const parsed = new URL(url);
    expect(parsed.searchParams.has("start_date")).toBe(false);
    expect(parsed.searchParams.has("end_date")).toBe(false);
  });

  it("manda o token como Bearer e lança erro em resposta não-ok", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse({ detail: "erro" }, 500));
    vi.stubGlobal("fetch", mockFetch);

    await expect(fetchAiUsageMetrics("mock-token", { period: "7d" })).rejects.toThrow();

    const [, init] = mockFetch.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer mock-token");
  });

  it("devolve o relatório quando a resposta é 200", async () => {
    const mockFetch = vi.fn().mockResolvedValue(jsonResponse(RELATORIO_VAZIO));
    vi.stubGlobal("fetch", mockFetch);

    const resultado = await fetchAiUsageMetrics("mock-token", { period: "7d" });

    expect(resultado).toEqual(RELATORIO_VAZIO);
  });
});
