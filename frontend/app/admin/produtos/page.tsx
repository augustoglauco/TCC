"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { fetchAdminProducts, deleteAdminProduct } from "@/lib/api/adminProducts";
import type { AdminProduct } from "@/lib/types/adminProducts";
import ProductListTable from "@/components/admin/products/ProductListTable";
import ProductFormModal from "@/components/admin/products/ProductFormModal";
import CatalogImportModal from "@/components/admin/products/CatalogImportModal";

const CATEGORIAS = [
  "Todas",
  "CFTV",
  "Alarmes",
  "Redes",
  "Controle de Acesso",
  "Automação",
  "Geral",
];

export default function AdminProdutosPage() {
  const [produtos, setProdutos] = useState<AdminProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [termo, setTermo] = useState("");
  const [categoria, setCategoria] = useState("Todas");

  // Modais
  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);

  const carregarProdutos = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAdminProducts({
        termo: termo.trim() || undefined,
        categoria: categoria !== "Todas" ? categoria : undefined,
      });
      setProdutos(data.items);
    } catch (err) {
      console.error("Erro ao carregar produtos:", err);
    } finally {
      setLoading(false);
    }
  }, [termo, categoria]);

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
    } catch (err) {
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

      {/* Filtros e Busca */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-gray-50/80 p-3 rounded-xl border border-gray-200">
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

        <div className="flex items-center gap-2 overflow-x-auto">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider whitespace-nowrap">
            Categoria:
          </span>
          <div className="flex items-center gap-1">
            {CATEGORIAS.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoria(cat)}
                className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-colors whitespace-nowrap ${
                  categoria === cat
                    ? "bg-blue-600 text-white shadow-2xs"
                    : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-100"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
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
        onSuccess={carregarProdutos}
        produtoParaEditar={editingProduct}
      />

      <CatalogImportModal
        isOpen={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSuccess={carregarProdutos}
      />
    </div>
  );
}
