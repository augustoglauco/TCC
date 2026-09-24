import { afterEach, describe, expect, it, vi } from "vitest";

import { generateId } from "@/lib/utils/generateId";

describe("generateId", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("usa crypto.randomUUID quando disponível (contexto seguro: https/localhost)", () => {
    const spy = vi
      .spyOn(crypto, "randomUUID")
      .mockReturnValue("11111111-1111-4111-8111-111111111111");

    expect(generateId()).toBe("11111111-1111-4111-8111-111111111111");
    expect(spy).toHaveBeenCalledOnce();
  });

  it("cai para um gerador próprio quando crypto.randomUUID não existe (contexto inseguro: LAN via HTTP)", () => {
    // Reproduz o cenário real: acessar o site pelo IP local via HTTP no
    // celular — a Web Crypto API não existe fora de um contexto seguro
    // (https/localhost), então `crypto.randomUUID` é `undefined`. Sem
    // fallback, isso derrubava o app inteiro (ver getOrCreateConversationId
    // em useChatStore, chamado num useEffect no ChatWidget montado na raiz).
    const original = crypto.randomUUID;
    // @ts-expect-error simula a ausência da API em contexto inseguro
    delete crypto.randomUUID;

    const id = generateId();

    expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);

    crypto.randomUUID = original;
  });

  it("gera ids diferentes a cada chamada no fallback", () => {
    const original = crypto.randomUUID;
    // @ts-expect-error simula a ausência da API em contexto inseguro
    delete crypto.randomUUID;

    const a = generateId();
    const b = generateId();

    expect(a).not.toBe(b);

    crypto.randomUUID = original;
  });
});
