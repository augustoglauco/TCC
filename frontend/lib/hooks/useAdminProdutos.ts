"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchAdminProducts,
  fetchAdminCategories,
  deleteAdminProduct,
} from "@/lib/api/adminProducts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type { AdminProduct } from "@/lib/types/adminProducts";

export const CATEGORIAS_PADRAO = [
  "acessórios",
  "Alarmes",
  "Automação",
  "CFTV",
  "Controle de Acesso",
  "geradores",
  "Geral",
  "Redes",
];

function ordenarCategorias(cats: Iterable<string>): string[] {
  return Array.from(new Set(cats))
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b, "pt-BR", { sensitivity: "base" }));
}

export interface MetricasProdutos {
  total: number;
  comFoto: number;
  margemMedia: string | null;
}

export function calcularMetricas(produtos: AdminProduct[]): MetricasProdutos {
  const margens = produtos
    .map((p) => {
      if (p.preco && p.preco_base_fornecedor && p.preco_base_fornecedor > 0) {
        return ((p.preco - p.preco_base_fornecedor) / p.preco_base_fornecedor) * 100;
      }
      return null;
    })
    .filter((m): m is number => m !== null);

  return {
    total: produtos.length,
    comFoto: produtos.filter((p) => p.imagem_url).length,
    margemMedia:
      margens.length > 0 ? (margens.reduce((a, b) => a + b, 0) / margens.length).toFixed(1) : null,
  };
}

/** Contagem de produtos por categoria nos dados atuais. */
export function contarPorCategoria(produtos: AdminProduct[]): Record<string, number> {
  return produtos.reduce<Record<string, number>>((acc, prod) => {
    const cat = prod.categoria?.trim() || "Geral";
    acc[cat] = (acc[cat] || 0) + 1;
    return acc;
  }, {});
}

export function useAdminProdutos() {
  const token = useAuthStore((s) => s.token);
  const [produtos, setProdutos] = useState<AdminProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [termo, setTermo] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [availableCategories, setAvailableCategories] = useState<string[]>(CATEGORIAS_PADRAO);

  const [formModalOpen, setFormModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<AdminProduct | null>(null);
  const [importModalOpen, setImportModalOpen] = useState(false);

  // Carrega categorias do backend e consolida com sugestões
  const carregarCategorias = useCallback(async () => {
    if (!token) return;
    try {
      const catsDoBanco = await fetchAdminCategories(token);
      setAvailableCategories(ordenarCategorias([...CATEGORIAS_PADRAO, ...catsDoBanco]));
    } catch (err) {
      console.warn("Não foi possível carregar categorias remotas:", err);
    }
  }, [token]);

  useEffect(() => {
    // Carga inicial dos dados (fetch assíncrono) — falso positivo conhecido de
    // `react-hooks/set-state-in-effect`, mesmo caso de `app/admin/ingestao/page.tsx`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    carregarCategorias();
  }, [carregarCategorias]);

  const carregarProdutos = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const data = await fetchAdminProducts(token, {
        termo: termo.trim() || undefined,
        categoria: selectedCategories.length > 0 ? selectedCategories.join(",") : undefined,
      });
      setProdutos(data.items);

      // Atualiza lista de categorias dinamicamente com as categorias que vieram dos produtos
      const categoriasDosProdutos = data.items
        .map((p) => p.categoria?.trim())
        .filter((c): c is string => Boolean(c));

      setAvailableCategories((prev) => ordenarCategorias([...prev, ...categoriasDosProdutos]));
    } catch (err) {
      console.error("Erro ao carregar produtos:", err);
    } finally {
      setLoading(false);
    }
  }, [termo, selectedCategories, token]);

  useEffect(() => {
    const timer = setTimeout(() => {
      carregarProdutos();
    }, 250);
    return () => clearTimeout(timer);
  }, [carregarProdutos]);

  const recarregar = () => {
    carregarProdutos();
    carregarCategorias();
  };

  const handleDelete = async (id: number) => {
    if (!token) return;
    try {
      await deleteAdminProduct(token, id);
      recarregar();
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

  const handleFormSuccess = (produtoAtualizado?: AdminProduct | null) => {
    if (produtoAtualizado) {
      setEditingProduct(produtoAtualizado);
    }
    recarregar();
  };

  const handleRemoveCategory = (catToRemove: string) => {
    setSelectedCategories((prev) => prev.filter((c) => c !== catToRemove));
  };

  return {
    produtos,
    loading,
    termo,
    setTermo,
    selectedCategories,
    setSelectedCategories,
    availableCategories,
    formModalOpen,
    setFormModalOpen,
    editingProduct,
    importModalOpen,
    setImportModalOpen,
    recarregar,
    handleDelete,
    handleEdit,
    handleNewProduct,
    handleFormSuccess,
    handleRemoveCategory,
  };
}
