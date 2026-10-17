"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Produto } from "@/lib/api/products";
import { useCartStore } from "@/lib/hooks/useCartStore";
import { useChatStore } from "@/lib/hooks/useChatStore";
import { resolveImageUrl } from "@/lib/utils/resolveImageUrl";
import { ProductCardImage } from "./ProductCardImage";

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

  const valorFormatado = (val: number) => {
    const numStr = val.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `R$ ${numStr}`;
  };

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
        {/* Cabeçalho do Card: Categoria e Badge de Estoque */}
        <div className="flex items-center justify-between gap-2 text-left">
          <span className="rounded-md bg-slate-100 border border-slate-200/80 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-600">
            {product.categoria}
          </span>

          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              emEstoque
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-amber-50 text-amber-700 border border-amber-200"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                emEstoque ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
              }`}
            />
            {emEstoque ? `Em estoque (${totalEstoque} un)` : "Sem estoque"}
          </span>
        </div>

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

        {/* Preço de Venda em R$ (alinhado à direita) */}
        <div className="mt-4 flex items-baseline justify-end gap-2 text-right">
          {product.preco_promocional ? (
            <>
              <span className="text-lg font-extrabold text-blue-700">
                {valorFormatado(product.preco_promocional)}
              </span>
              <span className="text-xs text-slate-400 line-through">
                {valorFormatado(product.preco)}
              </span>
            </>
          ) : (
            <span className="text-xl font-extrabold text-blue-700">
              {valorFormatado(product.preco)}
            </span>
          )}
        </div>
      </div>

      {/* Botões de Ação: Comprar e Cotação */}
      <div className="mt-5 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={handleBuy}
          disabled={!emEstoque}
          className={`flex items-center justify-center gap-1.5 rounded-xl py-2.5 px-3 text-xs font-bold transition-all cursor-pointer ${
            emEstoque
              ? "bg-blue-600 text-white hover:bg-blue-700 shadow-xs hover:shadow"
              : "bg-slate-200 text-slate-400 cursor-not-allowed"
          }`}
        >
          <span>🛒</span>
          <span>Comprar</span>
        </button>

        <button
          type="button"
          onClick={handleQuote}
          className="flex items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 py-2.5 px-3 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors cursor-pointer"
        >
          <span>💬</span>
          <span>Cotar</span>
        </button>
      </div>
    </div>
  );
}
