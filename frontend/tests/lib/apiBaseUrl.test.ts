import { afterEach, describe, expect, it, vi } from "vitest";

import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";

describe("getApiBaseUrl", () => {
  const originalEnv = process.env.NEXT_PUBLIC_API_BASE_URL;

  afterEach(() => {
    process.env.NEXT_PUBLIC_API_BASE_URL = originalEnv;
    vi.unstubAllGlobals();
  });

  it("usa NEXT_PUBLIC_API_BASE_URL quando definida", () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:8000";

    expect(getApiBaseUrl()).toBe("http://backend:8000");
  });

  it("remove barra(s) final(is) de NEXT_PUBLIC_API_BASE_URL para não duplicar no path", () => {
    // Achado no code-review (2026-09-24): "http://backend:8000/" + "/api/..."
    // vira "http://backend:8000//api/..." (barra dupla) nas chamadoras, que
    // o roteador do FastAPI não trata como a rota real — 404 silencioso.
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://backend:8000/";

    expect(getApiBaseUrl()).toBe("http://backend:8000");
  });

  it("deriva do hostname/protocolo da própria página quando a env var não está definida", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;

    expect(getApiBaseUrl()).toBe(`${window.location.protocol}//${window.location.hostname}:8000`);
  });

  it("usa https quando a página é servida via https (mixed content, achado no code-review 2026-09-24)", () => {
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    vi.stubGlobal("location", { protocol: "https:", hostname: "augustoglauco.duckdns.org" });

    expect(getApiBaseUrl()).toBe("https://augustoglauco.duckdns.org:8000");
  });
});
