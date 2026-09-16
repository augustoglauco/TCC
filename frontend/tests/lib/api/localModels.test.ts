import { afterEach, describe, expect, it, vi } from "vitest";

import { LocalModelsApiError, activateModel } from "@/lib/api/localModels";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), { status });
}

describe("activateModel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("extrai a mensagem de um erro 422 de validação do Pydantic (detail como array)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          { detail: [{ loc: ["body", "name"], msg: "name deve ter ao menos 1 caractere", type: "value_error" }] },
          422,
        ),
      ),
    );

    await expect(activateModel("")).rejects.toMatchObject({
      message: "name deve ter ao menos 1 caractere",
      status: 422,
    });
  });

  it("preserva a mensagem de erro específica em string vinda do backend", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "Modelo não encontrado." }, 404)));

    await expect(activateModel("modelo-x")).rejects.toMatchObject({
      message: "Modelo não encontrado.",
      status: 404,
    });
  });

  it("usa a mensagem genérica de fallback quando o backend não retorna detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({}, 500)));

    await expect(activateModel("modelo-x")).rejects.toBeInstanceOf(LocalModelsApiError);
    await expect(activateModel("modelo-x")).rejects.toMatchObject({
      message: "Não foi possível ativar o modelo. Tente novamente.",
    });
  });
});
