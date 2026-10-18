import { useMemo } from "react";
import { useRouter } from "next/navigation";
import { Produto } from "@/lib/api/products";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import {
  calcularEstoqueTotal,
  escolherCentroDistribuicao,
  montarListaImagens,
  precoEfetivo,
} from "@/components/products/productCardHelpers";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";

/** Dados derivados do produto (imagens, estoque) e as ações de compra/cotação da página. */
export function useProdutoAcoes(product: Produto | null) {
  const router = useRouter();

  const imageList = useMemo(() => (product ? montarListaImagens(product) : []), [product]);
  const totalEstoque = useMemo(
    () => (product ? calcularEstoqueTotal(product.estoques) : 0),
    [product],
  );

  const handleBuy = () => {
    if (!product) return;
    useCartStore.getState().addItem({
      produtoId: product.id,
      nome: product.nome,
      preco: precoEfetivo(product),
      imagemUrl: resolveImageUrl(product.imagem_url),
      quantidade: 1,
      centroDistribuicao: escolherCentroDistribuicao(product.estoques),
    });

    router.push("/pedidos");
  };

  const handleQuote = () => {
    useChatStore.getState().open();
  };

  return { imageList, totalEstoque, emEstoque: totalEstoque > 0, handleBuy, handleQuote };
}
