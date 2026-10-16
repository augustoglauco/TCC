import { afterEach, describe, expect, it, vi } from "vitest";

import { urlDeVisualizacao, type FerramentaStatus } from "@/lib/api/ferramentas";

function ferramenta(parcial: Partial<FerramentaStatus>): FerramentaStatus {
  return {
    id: "gitnexus",
    nome: "GitNexus",
    descricao: "Grafo de execução",
    tipo: "servidor",
    url: "http://localhost:4757",
    online: true,
    detalhe: null,
    comando: "gitnexus serve -p 4757",
    ...parcial,
  };
}

describe("urlDeVisualizacao", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("passa ?server= ao GitNexus apontando para a própria origem", () => {
    // A SPA do GitNexus chama o backend numa URL fixa de build
    // (http://localhost:4747) — o localhost do navegador. Sem o ?server= ela
    // fica presa no "Start your local server".
    vi.stubGlobal("location", { hostname: "localhost" });

    const url = new URL(urlDeVisualizacao(ferramenta({}), "tok") as string);

    expect(url.origin).toBe("http://localhost:4757");
    expect(url.searchParams.get("server")).toBe("http://localhost:4757");
  });

  it("de fora da rede, troca host e porta pelas públicas e aponta o ?server= para elas", () => {
    vi.stubGlobal("location", { hostname: "augustoglauco.duckdns.org" });

    const url = new URL(urlDeVisualizacao(ferramenta({}), "tok") as string);

    expect(url.origin).toBe("http://augustoglauco.duckdns.org:4747");
    expect(url.searchParams.get("server")).toBe("http://augustoglauco.duckdns.org:4747");
  });

  it("não acrescenta ?server= ao Repowise, que serve a UI e a API na mesma origem", () => {
    vi.stubGlobal("location", { hostname: "augustoglauco.duckdns.org" });

    const url = new URL(
      urlDeVisualizacao(
        ferramenta({
          id: "repowise",
          nome: "Repowise",
          url: "http://localhost:3012/repos/abc/overview",
        }),
        "tok",
      ) as string,
    );

    expect(url.origin).toBe("http://augustoglauco.duckdns.org:3002");
    expect(url.searchParams.has("server")).toBe(false);
  });

  it("mantém o token na query do artefato do Graphify (iframe não manda Authorization)", () => {
    const url = urlDeVisualizacao(
      ferramenta({
        id: "graphify",
        tipo: "artefato",
        url: "/api/admin/ferramentas/graphify/grafo",
      }),
      "tok en",
    );

    expect(url).toContain("/api/admin/ferramentas/graphify/grafo?token=tok%20en");
  });

  it("devolve null quando a ferramenta não tem o que abrir", () => {
    expect(urlDeVisualizacao(ferramenta({ url: null, online: false }), "tok")).toBeNull();
  });
});
