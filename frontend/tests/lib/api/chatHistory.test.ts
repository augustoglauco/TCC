import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchConversationHistory } from "@/lib/api/chat";

function mockFetch(resposta: Partial<Response> | Error) {
  vi.stubGlobal(
    "fetch",
    resposta instanceof Error
      ? vi.fn().mockRejectedValue(resposta)
      : vi.fn().mockResolvedValue(resposta as Response),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchConversationHistory (retomada da conversa, R9)", () => {
  it("converte as mensagens gravadas para o formato do chat", async () => {
    mockFetch({
      ok: true,
      status: 200,
      json: async () => ({
        conversation_id: "conv-1",
        resumo: null,
        mensagens: [
          {
            papel: "cliente",
            texto: "Quanto custa o GD-15?",
            dominio: null,
            criada_em: "x",
            metricas: null,
          },
          {
            papel: "assistente",
            texto: "R$ 24.900,00",
            dominio: "vendas",
            criada_em: "x",
            metricas: null,
          },
        ],
      }),
    });

    const historico = await fetchConversationHistory("conv-1");

    expect(historico?.map(({ role, text, domain }) => ({ role, text, domain }))).toEqual([
      { role: "user", text: "Quanto custa o GD-15?", domain: undefined },
      { role: "assistant", text: "R$ 24.900,00", domain: "vendas" },
    ]);
    expect(vi.mocked(fetch).mock.calls[0][0]).toMatch(/\/api\/chat\/conversations\/conv-1$/);
  });

  it("resposta com métricas gravadas volta com o painel completo, perfil incluído", async () => {
    mockFetch({
      ok: true,
      status: 200,
      json: async () => ({
        conversation_id: "conv-1",
        resumo: null,
        mensagens: [
          {
            papel: "assistente",
            texto: "R$ 24.900,00",
            dominio: "vendas",
            criada_em: "x",
            metricas: {
              domain: "vendas",
              backend_used: "local",
              escalation_reason: "nenhum",
              model_name: "gemma4:12b",
              latency_ms: 4200,
              perfil_usuario: "lead",
              perfil_motivo: "intenção de compra",
            },
          },
        ],
      }),
    });

    const [resposta] = (await fetchConversationHistory("conv-1")) ?? [];

    expect(resposta.backendUsed).toBe("local");
    expect(resposta.metrics).toMatchObject({
      modelName: "gemma4:12b",
      latencyMs: 4200,
      perfilUsuario: "lead",
      perfilMotivo: "intenção de compra",
    });
  });

  it("conversa que ainda não existe (404) devolve lista vazia", async () => {
    mockFetch({ ok: false, status: 404 });

    expect(await fetchConversationHistory("conv-nova")).toEqual([]);
  });

  it("erro do backend ou de rede devolve null, sem lançar", async () => {
    mockFetch({ ok: false, status: 503 });
    expect(await fetchConversationHistory("conv-1")).toBeNull();

    mockFetch(new TypeError("Failed to fetch"));
    expect(await fetchConversationHistory("conv-1")).toBeNull();
  });
});
