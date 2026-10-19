"use client";

import React from "react";
import {
  calcularMetricas,
  contarPorCategoria,
  useAdminProdutos,
} from "@/lib/hooks/useAdminProdutos";
import ProductListTable from "@/components/admin/products/ProductListTable";
import ProductFormModal from "@/components/admin/products/ProductFormModal";
import CatalogImportModal from "@/components/admin/products/CatalogImportModal";
import {
  ProdutosFiltros,
  ProdutosHeader,
  ProdutosMetricas,
} from "@/components/admin/products/ProdutosPageParts";

export default function AdminProdutosPage() {
  const p = useAdminProdutos();

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10 space-y-6">
      <ProdutosHeader onImport={() => p.setImportModalOpen(true)} onNew={p.handleNewProduct} />
      <ProdutosMetricas metricas={calcularMetricas(p.produtos)} />
      <ProdutosFiltros
        termo={p.termo}
        onTermoChange={p.setTermo}
        selectedCategories={p.selectedCategories}
        onCategoriesChange={p.setSelectedCategories}
        availableCategories={p.availableCategories}
        categoryCounts={contarPorCategoria(p.produtos)}
        onRemoveCategory={p.handleRemoveCategory}
      />

      <ProductListTable
        produtos={p.produtos}
        loading={p.loading}
        onEdit={p.handleEdit}
        onDelete={p.handleDelete}
      />

      <ProductFormModal
        isOpen={p.formModalOpen}
        onClose={() => p.setFormModalOpen(false)}
        onSuccess={p.handleFormSuccess}
        produtoParaEditar={p.editingProduct}
        allProducts={p.produtos}
      />

      <CatalogImportModal
        isOpen={p.importModalOpen}
        onClose={() => p.setImportModalOpen(false)}
        onSuccess={p.recarregar}
      />
    </div>
  );
}
