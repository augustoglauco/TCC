import { describe, it, expect } from "vitest";
import { montarPayloadProduto } from "@/lib/hooks/useProductFormSubmit";

const base = {
  nome: " Câmera ",
  categoria: " CFTV ",
  familia: "  ",
  preco: "199.9",
  precoBaseFornecedor: "",
  diasAlertaEstoque: "",
  descricao: " desc ",
  especificacoesTecnicas: "  ",
};

describe("montarPayloadProduto", () => {
  it("rejeita nome vazio", () => {
    expect(montarPayloadProduto({ ...base, nome: "  " })).toEqual({
      erro: "O nome do produto é obrigatório.",
    });
  });

  it.each(["", "abc", "-1"])("rejeita preço inválido %j", (preco) => {
    expect(montarPayloadProduto({ ...base, preco })).toEqual({
      erro: "Informe um preço de venda válido.",
    });
  });

  it("normaliza textos e converte opcionais vazios em null", () => {
    expect(montarPayloadProduto(base)).toEqual({
      payload: {
        nome: "Câmera",
        categoria: "CFTV",
        familia: null,
        preco: 199.9,
        preco_base_fornecedor: null,
        dias_alerta_estoque: null,
        descricao: "desc",
        especificacoes_tecnicas: null,
        dimensoes_cm: null,
        peso_kg: null,
      },
    });
  });

  it("envia dimensões e peso (aceita vírgula) e rejeita peso inválido", () => {
    expect(
      montarPayloadProduto({ ...base, dimensoesCm: " 12 x 8 x 3 ", pesoKg: "0,35" }),
    ).toMatchObject({ payload: { dimensoes_cm: "12 x 8 x 3", peso_kg: 0.35 } });
    for (const pesoKg of ["abc", "-1"]) {
      expect(montarPayloadProduto({ ...base, pesoKg })).toEqual({
        erro: "Informe um peso válido (kg).",
      });
    }
  });

  it("converte opcionais preenchidos e usa categoria padrão", () => {
    const r = montarPayloadProduto({
      ...base,
      categoria: " ",
      familia: " iDAccess ",
      precoBaseFornecedor: "50.5",
      diasAlertaEstoque: "7",
      especificacoesTecnicas: " 4K ",
    });
    expect(r).toMatchObject({
      payload: {
        categoria: "Geral",
        familia: "iDAccess",
        preco_base_fornecedor: 50.5,
        dias_alerta_estoque: 7,
        especificacoes_tecnicas: "4K",
      },
    });
  });
});
