import { describe, expect, it } from "vitest";
import type { Produto } from "@/lib/api/products";
import {
  calcularEstoqueTotal,
  escolherCentroDistribuicao,
  montarListaImagens,
  precoEfetivo,
} from "@/components/products/productCardHelpers";

const est = (quantidade: number, cd: string) => ({
  id: cd,
  quantidade,
  centro_distribuicao: cd,
  atualizado_em: "2026-10-18",
});

describe("productCardHelpers", () => {
  it("calcularEstoqueTotal ignora negativos e aceita vazio", () => {
    expect(calcularEstoqueTotal([est(5, "A"), est(-3, "B"), est(2, "C")])).toBe(7);
    expect(calcularEstoqueTotal([])).toBe(0);
    expect(calcularEstoqueTotal(undefined as unknown as Produto["estoques"])).toBe(0);
  });

  it("escolherCentroDistribuicao: com saldo, primeiro, padrão", () => {
    expect(escolherCentroDistribuicao([est(0, "A"), est(4, "B")])).toBe("B");
    expect(escolherCentroDistribuicao([est(0, "A"), est(0, "B")])).toBe("A");
    expect(escolherCentroDistribuicao([])).toBe("CD-SP");
  });

  it("precoEfetivo prefere promocional quando definido", () => {
    expect(precoEfetivo({ preco: 100, preco_promocional: 80 })).toBe(80);
    expect(precoEfetivo({ preco: 100, preco_promocional: null })).toBe(100);
  });

  it("montarListaImagens deduplica e coloca a principal primeiro", () => {
    const p = {
      imagem_url: "https://x/main.png",
      imagens: [{ imagem_url: "https://x/a.png" }, { imagem_url: "https://x/a.png" }],
    } as unknown as Produto;
    expect(montarListaImagens(p)).toEqual(["https://x/main.png", "https://x/a.png"]);
    // principal já presente na galeria mantém a posição original
    const q = { imagem_url: "https://x/m.png", imagens: [{ imagem_url: "https://x/a.png" }, { imagem_url: "https://x/m.png" }] } as unknown as Produto;
    expect(montarListaImagens(q)).toEqual(["https://x/a.png", "https://x/m.png"]);
    expect(montarListaImagens({ imagem_url: null, imagens: [] } as unknown as Produto)).toEqual([]);
  });
});
