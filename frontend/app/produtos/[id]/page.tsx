"use client";

import { use, useState } from "react";
import Link from "next/link";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";
import { ProdutoImageGallery } from "./ProdutoImageGallery";
import { ProdutoInfoPanel } from "./ProdutoInfoPanel";
import { ProdutoFichaTecnica } from "./ProdutoFichaTecnica";
import { ProdutoLoadingSkeleton } from "./ProdutoLoadingSkeleton";
import { ProdutoErrorState } from "./ProdutoErrorState";
import { useProduto } from "./useProduto";
import { useProdutoAcoes } from "./useProdutoAcoes";

interface ProdutoPageProps {
  params: Promise<{ id: string }> | { id: string };
}

export default function ProdutoDetalhePage({ params }: ProdutoPageProps) {
  const resolvedParams = "then" in params ? use(params) : params;
  const { id } = resolvedParams;
  const { product, loading, error } = useProduto(id);
  const [currentImgIndex, setCurrentImgIndex] = useState(0);

  // Estado para modal de zoom de imagem
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);

  const { imageList, totalEstoque, emEstoque, handleBuy, handleQuote } = useProdutoAcoes(product);

  if (loading) return <ProdutoLoadingSkeleton />;

  if (error || !product) return <ProdutoErrorState error={error} />;
  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-12">
      {/* Breadcrumb e Retorno */}
      <nav
        aria-label="Navegação estrutural"
        className="mb-6 flex items-center gap-2 text-xs sm:text-sm text-slate-500"
      >
        <Link href="/produtos" className="hover:text-blue-600 transition-colors font-medium">
          ← Catálogo de Produtos
        </Link>
        <span>/</span>
        <span className="text-slate-600 font-medium">{product.categoria}</span>
        <span>/</span>
        <span className="text-slate-900 font-semibold truncate max-w-xs">{product.nome}</span>
      </nav>

      {/* Grid Principal: Imagens + Informações Comerciais */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 lg:gap-12">
        <ProdutoImageGallery
          imageList={imageList}
          currentImgIndex={currentImgIndex}
          productName={product.nome}
          onSelectIndex={setCurrentImgIndex}
          onZoom={setZoomImageUrl}
        />

        <ProdutoInfoPanel
          product={product}
          emEstoque={emEstoque}
          totalEstoque={totalEstoque}
          onBuy={handleBuy}
          onQuote={handleQuote}
        />
      </div>

      <ProdutoFichaTecnica product={product} />

      {/* Modal de Zoom da Imagem */}
      {zoomImageUrl && (
        <ImageZoomModal
          imageUrl={zoomImageUrl}
          productName={product.nome}
          onClose={() => setZoomImageUrl(null)}
        />
      )}
    </div>
  );
}
