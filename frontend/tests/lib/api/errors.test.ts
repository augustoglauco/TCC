import { describe, expect, it } from "vitest";

import { extrairDetalheDeErro, extrairMensagemDeDetail } from "@/lib/api/errors";

function criarResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 422,
    ...init,
  });
}

describe("extrairMensagemDeDetail", () => {
  it("retorna a string diretamente quando detail é string", () => {
    expect(extrairMensagemDeDetail("Coleção não encontrada.")).toBe("Coleção não encontrada.");
  });

  it("junta as mensagens quando detail é um array de erros de validação do Pydantic", () => {
    const detail = [
      { loc: ["body", "chunk_size"], msg: "chunk_size deve ser maior que chunk_overlap", type: "value_error" },
      { loc: ["body", "collection_ids"], msg: "collection_ids deve ter ao menos 1 item", type: "value_error" },
    ];

    expect(extrairMensagemDeDetail(detail)).toBe(
      "chunk_size deve ser maior que chunk_overlap; collection_ids deve ter ao menos 1 item",
    );
  });

  it("ignora itens do array sem msg válido e ainda retorna os demais", () => {
    const detail = [{ loc: ["body", "name"] }, { msg: "name deve ter ao menos 1 caractere" }];

    expect(extrairMensagemDeDetail(detail)).toBe("name deve ter ao menos 1 caractere");
  });

  it("retorna undefined quando detail é um array vazio", () => {
    expect(extrairMensagemDeDetail([])).toBeUndefined();
  });

  it("retorna undefined quando detail é um array sem nenhum msg utilizável", () => {
    expect(extrairMensagemDeDetail([{ loc: ["body", "name"] }])).toBeUndefined();
  });

  it("retorna undefined quando detail é undefined", () => {
    expect(extrairMensagemDeDetail(undefined)).toBeUndefined();
  });

  it("retorna undefined quando detail tem um formato inesperado (objeto solto, número)", () => {
    expect(extrairMensagemDeDetail({ unexpected: true })).toBeUndefined();
    expect(extrairMensagemDeDetail(42)).toBeUndefined();
  });

  it("retorna undefined quando detail é string vazia", () => {
    expect(extrairMensagemDeDetail("")).toBeUndefined();
  });
});

describe("extrairDetalheDeErro", () => {
  it("extrai a string de um erro HTTPException simples", async () => {
    const response = criarResponse({ detail: "Não é possível excluir a collection ativa." });

    await expect(extrairDetalheDeErro(response)).resolves.toBe(
      "Não é possível excluir a collection ativa.",
    );
  });

  it("extrai e junta as mensagens de um erro 422 de validação do Pydantic (array)", async () => {
    const response = criarResponse({
      detail: [
        { loc: ["body", "name"], msg: "name deve ter ao menos 1 caractere", type: "value_error" },
      ],
    });

    await expect(extrairDetalheDeErro(response)).resolves.toBe("name deve ter ao menos 1 caractere");
  });

  it("retorna undefined (sem lançar) quando o corpo não é JSON válido", async () => {
    const response = new Response("não é json", { status: 500 });

    await expect(extrairDetalheDeErro(response)).resolves.toBeUndefined();
  });

  it("retorna undefined quando o corpo não tem detail", async () => {
    const response = criarResponse({});

    await expect(extrairDetalheDeErro(response)).resolves.toBeUndefined();
  });
});
