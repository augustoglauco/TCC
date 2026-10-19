"use client";

import { useState } from "react";
import { ImageZoomModal } from "@/components/products/ImageZoomModal";
import { CatalogoConteudo } from "./CatalogoConteudo";
import { CatalogoHeader } from "./CatalogoHeader";
import { PaginacaoProdutos } from "./PaginacaoProdutos";
import { useProdutosCatalogo } from "./useProdutosCatalogo";

export default function ProdutosPage() {
  const catalogo = useProdutosCatalogo();
  const { setCurrentPage, setSelectedCategory } = catalogo;

  // Estado para modal de zoom de imagem
  const [zoomImageUrl, setZoomImageUrl] = useState<string | null>(null);
  const [zoomProductName, setZoomProductName] = useState("");

  const handleOpenZoom = (url: string, nome: string) => {
    setZoomImageUrl(url);
    setZoomProductName(nome);
  };

  const handleCloseZoom = () => {
    setZoomImageUrl(null);
    setZoomProductName("");
  };

  const handleSelectCategory = (cat: string) => {
    setSelectedCategory(cat);
    setCurrentPage(1);
  };

  return (
    <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 sm:py-10 space-y-8">
      {zoomImageUrl && (
        <ImageZoomModal
          imageUrl={zoomImageUrl}
          productName={zoomProductName}
          onClose={handleCloseZoom}
        />
      )}

      <CatalogoHeader
        searchQuery={catalogo.searchQuery}
        onSearchChange={catalogo.setSearchQuery}
        categories={catalogo.categories}
        selectedCategory={catalogo.selectedCategory}
        onSelectCategory={handleSelectCategory}
        onOpenZoom={handleOpenZoom}
      />

      <CatalogoConteudo
        loading={catalogo.loading}
        error={catalogo.error}
        products={catalogo.products}
        groupedProducts={catalogo.groupedProducts}
        onRetry={() => setCurrentPage(1)}
        onOpenZoom={handleOpenZoom}
      />

      {!catalogo.loading && !catalogo.error && catalogo.totalItems > 0 && (
        <PaginacaoProdutos
          currentPage={catalogo.currentPage}
          totalPages={catalogo.totalPages}
          totalItems={catalogo.totalItems}
          onChange={setCurrentPage}
        />
      )}
    </div>
  );
}
