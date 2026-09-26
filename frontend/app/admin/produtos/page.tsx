"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchAdminProducts,
  fetchAdminCategories,
  deleteAdminProduct,
} from "@/lib/api/adminProducts";
import type { AdminProduct } from "@/lib/types/adminProducts";
import ProductListTable from "@/components/admin/products/ProductListTable";
import ProductFormModal from "@/components/admin/products/ProductFormModal";
import CatalogImportModal from "@/components/admin/products/CatalogImportModal";
import CategoryFilter from "@/components/admin/products/CategoryFilter";

const CATEGORIAS_PADRAO = [
  "CFTV",
  "Alarmes",
  "Redes",
  "Controle de Acesso",
  "Automação",
  "Geral",
  "geradores",
  "acessórios",
];

export default function AdminProdutosPage() {
  const [produtos, setProdutos] = useState<AdminProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [termo, setTermo] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>(CATEGORIAS_PADRAO);

  // Modais
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Carrega categorias do backend e consolida com sugestões
  const carregarCategorias = useCallback(async () => {
    try {
      const catsDoBanco = await fetchAdminCategories();
      const todas = Array.from(new Set([...CATEGORIAS_PADRAO, ...catsDoBanco])).filter(Boolean);
      setAvailableCategories(todas);
    } catch (err) {
      console.warn("Não foi possível carregar categorias remotas:", err);
    }
  }, []);

  useEffect(() => {
    carregarCategorias();
  }, [carregarCategorias]);

  const carregarProdutos = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAdminProducts({
        termo: termo.trim() || undefined,
        categoria: selectedCategories.length > 0 ? selectedCategories.join(",") : undefined,
      });
      setProdutos(data.items);

      // Atualiza lista de categorias dinamicamente com as categorias que vieram dos produtos
      const categoriasDosProdutos = data.items
        .map((p) => p.categoria?.trim())
        .filter((c): c is string => Boolean(c));

      setAvailableCategories((prev) =>
        Array.from(new Set([...prev, ...categoriasDosProdutos]))
      );
    } catch (err) {
      console.error("Erro ao carregar produtos:", err);
    } finally {
      setLoading(false);
    }
  }, [termo, selectedCategories]);

  useEffect(() => {
    const timer = setTimeout(() => {
      carregarProdutos();
    }, 250);
    return () => clearTimeout(timer);
  }, [carregarProdutos]);

  const handleDelete = async (id: number) => {
    try {
      await deleteAdminProduct(id);
      carregarProdutos();
      carregarCategorias();
    } catch {
      alert("Erro ao excluir produto. Tente novamente.");
    }
  };

  const handleEdit = (p: AdminProduct) => {
    setEditingProduct(p);
    setFormModalOpen(true);
  };

  const handleNewProduct = () => {
    setEditingProduct(null);
    setFormModalOpen(true);
  };

  const handleRemoveCategory = (catToRemove: string) => {
    setSelectedCategories((prev) => prev.filter((c) => c !== catToRemove));
  };

  // Contagem de produtos por categoria nos dados atuais
  const categoryCounts = produtos.reduce<Record<string, number>>((acc, prod) => {
    const cat = prod.categoria?.trim() || "Geral";
    acc[cat] = (acc[cat] || 0) + 1;
    return acc;
  }, {});

  // Métricas rápidas
  const totalProdutos = produtos.length;
  const produtosComFoto = produtos.filter((p) => p.imagem_url).length;
  const margensValidas = produtos
    .map((p) => {
      if (p.preco && p.preco_base_fornecedor && p.preco_base_fornecedor > 0) {
        return ((p.preco - p.preco_base_fornecedor) / p.preco_base_fornecedor) * 100;
      }
      return null;
    })
    .filter((m): m is number => m !== null);

  const margemMedia =
    margensValidas.length > 0
      ? (margensValidas.reduce((a, b) => a + b, 0) / margensValidas.length).toFixed(1)
      : null;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:py-10 space-y-6">
      {/* Header com breadcrumb / links */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-200 pb-5">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1">
            <Link href="/" className="hover:text-blue-600 transition-colors">
              Chat
            </Link>
            <span>/</span>
            <Link href="/admin/modelos" className="hover:text-blue-600 transition-colors">
              Admin
            </Link>
            <span>/</span>
            <span className="text-blue-600">Catálogo de Produtos</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900">
            Catálogo de Produtos
          </h1>
          <p className="text-xs sm:text-sm text-gray-500 mt-0.5">
            Cadastre produtos, custos e fotos vetorizadas no catálogo visual CLIP para atendimento inteligente no chat.
          </p>
        </div>

        {/* Ações principais */}
        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={() => setImportModalOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3.5 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
          >
            <span>📥</span>
            <span>Importar Catálogo (PDF/Fotos)</span>
          </button>
          <button
            type="button"
            onClick={handleNewProduct}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 transition-colors"
          >
            <span>+</span>
            <span>Novo Produto</span>
          </button>
        </div>
      </div>

      {/* Cards de Métricas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Total de Produtos
          </div>
          <div className="mt-1 text-2xl font-bold text-gray-900">{totalProdutos}</div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Com Foto / Vetorizados no CLIP
          </div>
          <div className="mt-1 text-2xl font-bold text-emerald-600 flex items-center gap-1.5">
            <span>{produtosComFoto}</span>
            <span className="text-xs font-medium text-gray-400">
              ({totalProdutos > 0 ? Math.round((produtosComFoto / totalProdutos) * 100) : 0}%)
            </span>
          </div>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-2xs">
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Margem de Lucro Média
          </div>
          <div className="mt-1 text-2xl font-bold text-blue-600">
            {margemMedia !== null ? `+${margemMedia}%` : "-"}
          </div>
        </div>
      </div>

      {/* Barra de Filtros e Busca */}
      <div className="bg-gray-50/90 p-4 rounded-xl border border-gray-200 space-y-3">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {/* Campo de Busca Livre */}
          <div className="relative flex-1">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
              🔍
            </span>
            <input
              type="text"
              value={termo}
              onChange={(e) => setTermo(e.target.value)}
              placeholder="Buscar por nome, modelo, especificações ou descrição..."
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Controle Visual de Seleção Múltipla de Categorias */}
          <CategoryFilter
            selectedCategories={selectedCategories}
            onChange={setSelectedCategories}
            availableCategories={availableCategories}
            categoryCounts={categoryCounts}
          />
        </div>

        {/* Badges de Categorias Selecionadas Ativas */}
        {selectedCategories.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-gray-200/70">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
              Filtros ativos ({selectedCategories.length}):
            </span>
            {selectedCategories.map((cat) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1.5 rounded-full bg-blue-100/80 border border-blue-200 px-3 py-0.5 text-xs font-semibold text-blue-800"
              >
                <span>{cat}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveCategory(cat)}
                  className="rounded-full text-blue-600 hover:bg-blue-200 hover:text-blue-900 h-3.5 w-3.5 inline-flex items-center justify-center transition-colors"
                  title={`Remover filtro ${cat}`}
                >
                  ✕
                </button>
              </span>
            ))}
            <button
              type="button"
              onClick={() => setSelectedCategories([])}
              className="text-xs font-medium text-red-600 hover:text-red-800 underline transition-colors ml-1"
            >
              Limpar todas
            </button>
          </div>
        )}
      </div>

      {/* Tabela de Produtos */}
      <ProductListTable
        produtos={produtos}
        loading={loading}
        onEdit={handleEdit}
        onDelete={handleDelete}
      />

      {/* Modais */}
      <ProductFormModal
        isOpen={formModalOpen}
        onClose={() => setFormModalOpen(false)}
        onSuccess={() => {
          carregarProdutos();
          carregarCategorias();
        }}
        produtoParaEditar={editingProduct}
      />

      <CatalogImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={() => {
          carregarProdutos();
          carregarCategorias();
        }}
      />
    </div>
  );
}
