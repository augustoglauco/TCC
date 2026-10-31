import { afterEach, describe, expect, it, vi } from "vitest";

import { uploadDocument } from "@/lib/api/rag";

function respostaOk() {
  return new Response(JSON.stringify({ filename: "a.md", domain: "vendas", chunks: 1 }), {
    status: 200,
  });
}

describe("uploadDocument", () => {
  afterEach(() => vi.restoreAllMocks());

  it("envia o arquivo de download como download_file quando informado", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(respostaOk());
    const md = new File(["# a"], "a.md");
    const pdf = new File(["%PDF"], "a.pdf");

    await uploadDocument("tok", { file: md, domain: "vendas", downloadFile: pdf });

    const body = fetchMock.mock.calls[0][1]?.body as FormData;
    expect((body.get("file") as File).name).toBe("a.md");
    expect((body.get("download_file") as File).name).toBe("a.pdf");
  });

  it("não envia download_file quando não informado", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(respostaOk());

    await uploadDocument("tok", { file: new File(["# a"], "a.md"), domain: "vendas" });

    const body = fetchMock.mock.calls[0][1]?.body as FormData;
    expect(body.has("download_file")).toBe(false);
  });
});
