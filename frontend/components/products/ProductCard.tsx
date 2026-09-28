"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import { Produto } from "@/lib/api/products";
import { useChatStore } from "@/lib/hooks/useChatStore";

interface ProductCardProps {
  product: Produto;
  onOpenZoom: (imageUrl: string) => void;
}

export function ProductCard({ product, onOpenZoom }: ProductCardProps) {
  const router = useRouter();

  // Helper para resolver URL completa da imagem (ex: /api/uploads/... -> http://localhost:8000/api/uploads/...)
  const resolveImageUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;
    if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:"))
      return url;
    const baseUrl = getApiBaseUrl();
    const cleanPath = url.startsWith("/") ? url : `/${url}`;
    return `${baseUrl}${cleanPath}`;
  };

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

  // Formata o preço usando o prefixo R$ e alinhamento correto
  const valorFormatado = (val: number) => {
    const numStr = val.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `R$ ${numStr}`;
  };

  const activeImageUrl = imageList[currentImgIndex] || null;

  const handlePrevImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev === 0 ? imageList.length - 1 : prev - 1));
  };

  const handleNextImage = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev === imageList.length - 1 ? 0 : prev + 1));
  };

  const handleBuy = () => {
    router.push(`/pedidos?produto=${product.id}`);
  };

  const handleQuote = () => {
    useChatStore.getState().open();
  };

  return (
    <div
      className={`group flex flex-col justify-between rounded-xl border bg-white p-5 text-left shadow-xs transition-all duration-200 hover:-translate-y-1 hover:shadow-md ${
        emEstoque
          ? "border-slate-200 hover:border-blue-300"
          : "border-slate-200 bg-slate-50/50 opacity-90"
      }`}
    >
      <div className="text-left">
        {/* Cabeçalho do Card: Categoria e Badge de Estoque */}
        <div className="flex items-center justify-between gap-2 text-left">
          <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600">
            {product.categoria}
          </span>

          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              emEstoque
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-amber-50 text-amber-700 border border-amber-200"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${emEstoque ? "bg-emerald-500" : "bg-amber-500"}`}
            />
            {emEstoque ? `Em estoque (${totalEstoque} un)` : "Sem estoque"}
          </span>
        </div>

        {/* Área da Imagem do Produto */}
        <div className="relative mt-4 aspect-4/3 w-full overflow-hidden rounded-lg bg-slate-100 flex items-center justify-center group/img border border-slate-100">
          {activeImageUrl ? (
            // eslint-disable-next-html-element-suppression
            <img
              src={activeImageUrl}
              alt={product.nome}
              className="h-full w-full object-contain p-2 transition-transform duration-300 group-hover/img:scale-105 cursor-pointer"
              onClick={() => onOpenZoom(activeImageUrl)}
            />
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-400 p-4 text-center">
              <svg
                className="h-10 w-10 text-slate-300"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              <span className="mt-1 text-xs text-slate-400">Sem foto cadastrada</span>
            </div>
          )}

          {/* Botão de Zoom na imagem */}
          {activeImageUrl && (
            <button
              type="button"
              onClick={() => onOpenZoom(activeImageUrl)}
              className="absolute top-2 right-2 rounded-full bg-slate-900/60 p-1.5 text-white opacity-0 group-hover/img:opacity-100 transition-opacity hover:bg-slate-900 cursor-pointer"
              title="Ampliar imagem (Zoom)"
              aria-label="Ampliar imagem"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
                />
              </svg>
            </button>
          )}

          {/* Navegação entre Múltiplas Imagens (Setas Esquerda / Direita) */}
          {imageList.length > 1 && (
            <>
              <button
                type="button"
                onClick={handlePrevImage}
                className="absolute left-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
                aria-label="Imagem anterior"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>

              <button
                type="button"
                onClick={handleNextImage}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
                aria-label="Próxima imagem"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2.5}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>

              {/* Indicador de fotos (1/3) */}
              <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 rounded-full bg-slate-900/70 px-2 py-0.5 text-[10px] text-white">
                {currentImgIndex + 1} / {imageList.length}
              </div>
            </>
          )}
        </div>

        {/* Nome do Produto (alinhado à esquerda) */}
        <h3 className="mt-3.5 font-bold text-slate-900 text-base line-clamp-2 min-h-12 leading-snug text-left">
          {product.nome}
        </h3>

        {/* Descrição Curta (alinhada à esquerda) */}
        {product.descricao && (
          <p className="mt-1 text-xs text-slate-500 line-clamp-2 min-h-8 text-left">
            {product.descricao}
          </p>
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
          className={`flex items-center justify-center gap-1.5 rounded-lg py-2.5 px-3 text-xs font-bold transition-all cursor-pointer ${
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
          className="flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-slate-50 py-2.5 px-3 text-xs font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors cursor-pointer"
        >
          <span>💬</span>
          <span>Cotar</span>
        </button>
      </div>
    </div>
  );
}
