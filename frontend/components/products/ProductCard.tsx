"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Produto } from "@/lib/api/products";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";
import { ProductCardImage } from "./ProductCardImage";
import { ProductCardHeader } from "./ProductCardHeader";
import { ProductCardPrice } from "./ProductCardPrice";
import { ProductCardActions } from "./ProductCardActions";

interface ProductCardProps {
  product: Produto;
  onOpenZoom: (imageUrl: string) => void;
}

export function ProductCard({ product, onOpenZoom }: ProductCardProps) {
  const router = useRouter();

  // Lista consolidada de URLs de imagem completas
  const imageList = useMemo(() => {
    const urls: string[] = [];
    if (product.imagens && product.imagens.length > 0) {
      product.imagens.forEach((img) => {
        const full = resolveImageUrl(img.imagem_url);
        if (full && !urls.includes(full)) {
          urls.push(full);
        }
      });
    }
    const mainFull = resolveImageUrl(product.imagem_url);
    if (mainFull && !urls.includes(mainFull)) {
      urls.unshift(mainFull); // Coloca imagem principal como primeira
    }
    return urls;
  }, [product]);

  const [currentImgIndex, setCurrentImgIndex] = useState(0);

  // Calcula estoque total
  const totalEstoque = useMemo(() => {
    if (!product.estoques || product.estoques.length === 0) return 0;
    return product.estoques.reduce(
      (acc, est) => acc + (est.quantidade > 0 ? est.quantidade : 0),
      0,
    );
  }, [product.estoques]);

  const emEstoque = totalEstoque > 0;

  const handlePrevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev === 0 ? imageList.length - 1 : prev - 1));
  };

  const handleNextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev === imageList.length - 1 ? 0 : prev + 1));
  };

  const handleBuy = () => {
    const cd =
      product.estoques && product.estoques.length > 0
        ? product.estoques.find((e) => e.quantidade > 0)?.centro_distribuicao ||
          product.estoques[0].centro_distribuicao
        : "CD-SP";

    const precoEfetivo = product.preco_promocional || product.preco;

    useCartStore.getState().addItem({
      produtoId: product.id,
      nome: product.nome,
      preco: Number(precoEfetivo),
      imagemUrl: resolveImageUrl(product.imagem_url),
      quantidade: 1,
      centroDistribuicao: cd,
    });

    router.push("/pedidos");
  };

  const handleQuote = () => {
    useChatStore.getState().open();
  };

  return (
    <div
      className={`group flex flex-col justify-between rounded-2xl border bg-white p-5 text-left shadow-xs transition-all duration-200 hover:-translate-y-1 hover:shadow-lg ${
        emEstoque
          ? "border-slate-200 hover:border-blue-400"
          : "border-slate-200 bg-slate-50/60 opacity-90"
      }`}
    >
      <div className="text-left">
        <ProductCardHeader
          categoria={product.categoria}
          emEstoque={emEstoque}
          totalEstoque={totalEstoque}
        />

        <ProductCardImage
          imageList={imageList}
          currentImgIndex={currentImgIndex}
          productName={product.nome}
          onZoom={onOpenZoom}
          onPrev={handlePrevImage}
          onNext={handleNextImage}
        />

        {/* Nome do Produto (alinhado à esquerda) */}
        <h3 className="mt-4 font-bold text-slate-900 text-base line-clamp-2 min-h-12 leading-snug text-left">
          <Link href={`/produtos/${product.id}`} className="hover:text-blue-600 transition-colors">
            {product.nome}
          </Link>
        </h3>

        {/* Descrição Curta (alinhada à esquerda) */}
        {product.descricao && (
          <p className="mt-1 text-xs text-slate-500 line-clamp-2 min-h-8 text-left">
            {product.descricao}
          </p>
        )}

        {/* Especificações Técnicas Resumidas */}
        {product.especificacoes_tecnicas && (
          <div className="mt-2.5 rounded-lg bg-slate-50 border border-slate-100 px-2.5 py-1.5 text-[11px] font-mono text-slate-600 line-clamp-1">
            {product.especificacoes_tecnicas}
          </div>
        )}

        <ProductCardPrice preco={product.preco} precoPromocional={product.preco_promocional} />
      </div>

      <ProductCardActions emEstoque={emEstoque} onBuy={handleBuy} onQuote={handleQuote} />
    </div>
  );
}
