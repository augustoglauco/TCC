import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchItens,
  fetchTarefa,
  revisarItem,
  iniciarTarefa,
  type ItemRevisao,
} from "@/lib/api/datasets";

const ITEM: ItemRevisao = { indice: 3, id: "r12", status: "aprovado", campos: {} };

function respostaOk(corpo: unknown) {
  return { ok: true, json: async () => corpo } as Response;
}

describe("cliente de /api/admin/datasets", () => {
  const fetchSpy = vi.fn();

  beforeEach(() => {
    fetchSpy.mockReset();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("revisarItem sem correção manda só o status", async () => {
    fetchSpy.mockResolvedValue(respostaOk(ITEM));

    await revisarItem("rag_docs", 3, "aprovado", "tok");

    const [, init] = fetchSpy.mock.calls[0];
    expect(init.method).toBe("PATCH");
    // Aprovar um item intacto não deve reescrever campo nenhum: o backend
    // faz `update`, e mandar `campos` gravaria o item de volta por nada.
    expect(JSON.parse(init.body)).toEqual({ status: "aprovado" });
  });

  it("revisarItem com correção manda os campos editados", async () => {
    fetchSpy.mockResolvedValue(respostaOk(ITEM));

    await revisarItem("rag_docs", 3, "corrigido", "tok", { pergunta: "nova?" });

    const [, init] = fetchSpy.mock.calls[0];
    expect(JSON.parse(init.body)).toEqual({ status: "corrigido", campos: { pergunta: "nova?" } });
  });

  it("fetchItens pede só os pendentes por padrão", async () => {
    fetchSpy.mockResolvedValue(respostaOk({ conjunto: "roteador", total: 0, itens: [] }));

    await fetchItens("roteador", "tok");

    const url = new URL(fetchSpy.mock.calls[0][0]);
    expect(url.pathname).toBe("/api/admin/datasets/roteador/itens");
    expect(url.searchParams.get("apenas_pendentes")).toBe("true");
    expect(url.searchParams.get("limite")).toBe("20");
  });

  it("fetchTarefa passa o offset do log já exibido", async () => {
    fetchSpy.mockResolvedValue(respostaOk({ linhas: [], proximo_offset: 40 }));

    await fetchTarefa("abc123", 40, "tok");

    expect(new URL(fetchSpy.mock.calls[0][0]).searchParams.get("desde")).toBe("40");
  });

  it("propaga o detalhe do backend quando a requisição falha", async () => {
    // O 409 de "triagem já está rodando" é informação para o operador: uma
    // mensagem genérica esconderia que a tarefa está no ar.
    fetchSpy.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ detail: "triagem já está rodando." }),
    } as Response);

    await expect(iniciarTarefa("triagem", "tok")).rejects.toThrow("triagem já está rodando.");
  });

  it("manda o token de admin no Authorization", async () => {
    fetchSpy.mockResolvedValue(respostaOk({ conjuntos: [] }));

    await fetchItens("injecao", "tok-admin");

    expect(fetchSpy.mock.calls[0][1].headers.Authorization).toBe("Bearer tok-admin");
  });
});
