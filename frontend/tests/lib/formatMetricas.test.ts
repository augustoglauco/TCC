import { describe, expect, it } from "vitest";
import {
  formatarCusto,
  formatarTokens,
  NAO_MEDIDO,
} from "@/lib/format/metricas";

describe("formatarCusto", () => {
  it("mostra zero conhecido como valor monetário, não como traço", () => {
    // 0.0 no ledger significa "grátis" (CLIP, modelo local) — é um número
    // medido, não ausência de medição.
    expect(formatarCusto(0)).toBe("$0.0000");
  });

  it("mostra não-medido como traço, não como zero", () => {
    expect(formatarCusto(null)).toBe(NAO_MEDIDO);
    expect(formatarCusto(undefined)).toBe(NAO_MEDIDO);
  });

  it("formata custo com 4 casas", () => {
    expect(formatarCusto(0.00254)).toBe("$0.0025");
    expect(formatarCusto(1.5)).toBe("$1.5000");
  });
});

describe("formatarTokens", () => {
  it("distingue zero medido de não-medido", () => {
    expect(formatarTokens(0)).toBe("0");
    expect(formatarTokens(null)).toBe(NAO_MEDIDO);
  });

  it("usa separador de milhar pt-BR", () => {
    expect(formatarTokens(1234567)).toBe((1234567).toLocaleString("pt-BR"));
  });
});
