"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchProductCategories, fetchProducts, Produto } from "@/lib/api/products";

export const ITEMS_PER_PAGE = 12;

export function useProdutosCatalogo() {
  const [products, setProducts] = useState<Produto[]>([]);
  const [categories, setCategories] = useState<string[]>(["Todas"]);
  const [totalItems, setTotalItems] = useState(0);

  const [selectedCategory, setSelectedCategory] = useState("Todas");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Debounce do campo de busca (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
      setCurrentPage(1); // Reseta para primeira página ao buscar
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Carrega categorias distintas na montagem
  useEffect(() => {
    fetchProductCategories()
      .then((cats) => setCategories(["Todas", ...cats]))
      .catch((err) => console.error("Falha ao carregar categorias:", err));
  }, []);

  // Carrega lista de produtos do backend (com filtro, busca e paginação de servidor)
  useEffect(() => {
    let isMounted = true;
    // Liga o indicador de carregamento antes do fetch — falso positivo conhecido
    // de `react-hooks/set-state-in-effect`, mesmo caso de `app/admin/ingestao/page.tsx`.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);

    const offset = (currentPage - 1) * ITEMS_PER_PAGE;

    fetchProducts({
      termo: debouncedSearch,
      categoria: selectedCategory,
      limit: ITEMS_PER_PAGE,
      offset,
    })
      .then((data) => {
        if (isMounted) {
          setProducts(data.items);
          setTotalItems(data.total);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          console.error("Erro ao carregar catálogo:", err);
          setError("Não foi possível carregar o catálogo de produtos do servidor.");
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [debouncedSearch, selectedCategory, currentPage]);

  // Agrupa os produtos da página atual por Categoria
  const groupedProducts = useMemo(() => {
    const groups: Record<string, Produto[]> = {};
    products.forEach((prod) => {
      const cat = prod.categoria || "Outros";
      if (!groups[cat]) {
        groups[cat] = [];
      }
      groups[cat].push(prod);
    });
    return groups;
  }, [products]);

  // Total de páginas
  const totalPages = Math.ceil(totalItems / ITEMS_PER_PAGE) || 1;

  return {
    products,
    categories,
    totalItems,
    totalPages,
    groupedProducts,
    selectedCategory,
    setSelectedCategory,
    searchQuery,
    setSearchQuery,
    currentPage,
    setCurrentPage,
    loading,
    error,
  };
}
