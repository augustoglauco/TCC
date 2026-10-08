import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { exportMetricsToCsv, exportMetricsToJson } from "@/lib/utils/exportMetrics";
import type { ChatUIMessage } from "@/lib/types/chat";

const mensagens: ChatUIMessage[] = [
  { id: "1", role: "user", text: "Qual o preço do Gerador GD-15?" },
  {
    id: "2",
    role: "assistant",
    text: "O Gerador GD-15 custa R$ 24.900,00.",
    domain: "vendas",
    backendUsed: "local",
    metrics: {
      modelName: "gemma4:12b-it-q4_K_M",
      promptTokens: 120,
      completionTokens: 40,
      latencyMs: 850,
      ttftMs: 120,
      tps: 47,
      confidence: 0.9,
      complexity: "baixa",
      estimatedCostUsd: 0,
      ragRetrievalMs: null,
      ragChunksCount: null,
      ragAvgScore: null,
      ragChunks: null,
      escalationReason: "nenhum",
    },
  },
  {
    id: "3",
    role: "atendente",
    text: "Um atendente irá atendê-lo agora.",
    atendenteNome: "Ana",
  },
];

// jsdom's Blob não implementa .text()/.arrayBuffer() de forma compatível com
// o Response deste ambiente de teste — captura o conteúdo direto na
// construção do Blob (síncrono), sem precisar "ler" a instância depois.
function capturarConteudoDoBlob(): { obter: () => string } {
  let conteudo = "";
  class BlobFalso {
    constructor(partes: string[]) {
      conteudo = partes.join("");
    }
  }
  vi.stubGlobal("Blob", BlobFalso);
  vi.stubGlobal("URL", {
    createObjectURL: () => "blob:fake",
    revokeObjectURL: vi.fn(),
  });
  return { obter: () => conteudo };
}

describe("exportMetricsToJson", () => {
  beforeEach(() => {
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("inclui mensagens de todos os papéis (cliente, assistente, atendente), não só assistente", () => {
    const blob = capturarConteudoDoBlob();
    exportMetricsToJson(mensagens);
    const conteudo = JSON.parse(blob.obter());

    expect(conteudo).toHaveLength(3);
    expect(conteudo.map((item: { role: string }) => item.role)).toEqual([
      "user",
      "assistant",
      "atendente",
    ]);
  });

  it("inclui o texto da mensagem, não só o comprimento", () => {
    const blob = capturarConteudoDoBlob();
    exportMetricsToJson(mensagens);
    const conteudo = JSON.parse(blob.obter());

    expect(conteudo[0].text).toBe("Qual o preço do Gerador GD-15?");
    expect(conteudo[1].text).toBe("O Gerador GD-15 custa R$ 24.900,00.");
  });

  it("mensagens sem métricas (cliente/atendente) exportam campos de métrica como null, sem quebrar", () => {
    const blob = capturarConteudoDoBlob();
    exportMetricsToJson(mensagens);
    const conteudo = JSON.parse(blob.obter());

    expect(conteudo[0].model_name).toBeNull();
    expect(conteudo[0].prompt_tokens).toBeNull();
    expect(conteudo[2].model_name).toBeNull();
  });
});

describe("exportMetricsToCsv", () => {
  let linkClicado: HTMLAnchorElement | null;

  beforeEach(() => {
    linkClicado = null;
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      linkClicado = this;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("inclui linhas para todos os papéis, não só assistente", () => {
    exportMetricsToCsv(mensagens);

    expect(linkClicado).not.toBeNull();
    const href = decodeURIComponent(linkClicado!.getAttribute("href") ?? "");
    const linhas = href.replace("data:text/csv;charset=utf-8,", "").split("\n");
    // 1 linha de header + 3 mensagens
    expect(linhas).toHaveLength(4);
    expect(linhas[1]).toContain("user");
    expect(linhas[2]).toContain("assistant");
    expect(linhas[3]).toContain("atendente");
  });
});
