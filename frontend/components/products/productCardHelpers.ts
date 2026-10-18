import type { Produto } from "@/lib/api/products";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";

const CD_PADRAO = "CD-SP";

/** URLs completas e sem repetição; a imagem principal vem primeiro. */
export function montarListaImagens(product: Produto): string[] {
  const urls: string[] = [];
  for (const img of product.imagens ?? []) {
    const full = resolveImageUrl(img.imagem_url);
    if (full && !urls.includes(full)) urls.push(full);
  }
  const mainFull = resolveImageUrl(product.imagem_url);
  if (mainFull && !urls.includes(mainFull)) urls.unshift(mainFull);
  return urls;
}

/** Soma das quantidades positivas de todos os centros de distribuição. */
export function calcularEstoqueTotal(estoques: Produto["estoques"]): number {
  return (estoques ?? []).reduce((acc, est) => acc + Math.max(est.quantidade, 0), 0);
}

/** CD com saldo; senão o primeiro cadastrado; senão o padrão. */
export function escolherCentroDistribuicao(estoques: Produto["estoques"]): string {
  if (!estoques || estoques.length === 0) return CD_PADRAO;
  return estoques.find((e) => e.quantidade > 0)?.centro_distribuicao || estoques[0].centro_distribuicao;
}

export function precoEfetivo(product: Pick<Produto, "preco" | "preco_promocional">): number {
  return Number(product.preco_promocional || product.preco);
}
