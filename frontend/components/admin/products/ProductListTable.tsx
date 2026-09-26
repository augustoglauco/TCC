"use client";

import React from "react";
import Image from "next/image";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import type { AdminProduct } from "@/lib/types/adminProducts";

interface ProductListTableProps {
  produtos: AdminProduct[];
  loading: boolean;
  onEdit: (produto: AdminProduct) => void;
  onDelete: (id: number) => void;
}

export default function ProductListTable({
  produtos,
  loading,
  onEdit,
  onDelete,
}: ProductListTableProps) {
  const getFullImageUrl = (url: string | null) => {
    if (!url) return null;
    if (url.startsWith("http://") || url.startsWith("https://")) return url;
    return `${getApiBaseUrl()}${url}`;
  };

  const formatCurrency = (val: number | null | undefined) => {
    if (val === null || val === undefined || isNaN(val)) return "-";
    return new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(val);
  };

  const calculateMargin = (venda: number | null, base: number | null) => {
    if (!venda || !base || base <= 0) return null;
    const margin = ((venda - base) / base) * 100;
    return margin.toFixed(1);
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-gray-200 bg-white">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
          <p className="text-sm font-medium text-gray-500">Carregando catálogo...</p>
        </div>
      </div>
    );
  }

  if (produtos.length === 0) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-blue-100 text-blue-600">
          📦
        </div>
        <h3 className="mt-3 text-base font-semibold text-gray-900">
          Nenhum produto cadastrado
        </h3>
        <p className="mt-1 text-sm text-gray-500 max-w-sm">
          Cadastre seu primeiro produto manualmente ou importe produtos em lote através de catálogos em PDF ou imagens.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50/75 text-xs font-semibold uppercase tracking-wider text-gray-500">
              <th className="py-3.5 pl-4 pr-3">Foto / CLIP</th>
              <th className="px-3 py-3.5">Nome e Descrição</th>
              <th className="px-3 py-3.5">Categoria</th>
              <th className="px-3 py-3.5">Preço Fornecedor</th>
              <th className="px-3 py-3.5">Preço Venda</th>
              <th className="px-3 py-3.5">Margem</th>
              <th className="py-3.5 pl-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {produtos.map((p) => {
              const fullImg = getFullImageUrl(p.imagem_url);
              const margin = calculateMargin(p.preco, p.preco_base_fornecedor);
              const temClip = (p.imagens && p.imagens.length > 0 && p.imagens.some(img => img.clip_image_id)) || Boolean(p.imagem_url);

              return (
                <tr key={p.id} className="hover:bg-gray-50/60 transition-colors">
                  <td className="py-3.5 pl-4 pr-3 whitespace-nowrap">
                    <div className="relative h-14 w-14 overflow-hidden rounded-lg border border-gray-200 bg-gray-100 flex items-center justify-center">
                      {fullImg ? (
                        <img
                          src={fullImg}
                          alt={p.nome}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <span className="text-2xl text-gray-400">📷</span>
                      )}
                      {temClip && (
                        <span
                          title="Vetorizado no catálogo visual CLIP (busca por foto no chat)"
                          className="absolute bottom-0.5 right-0.5 rounded bg-emerald-600 px-1 py-0.2 text-[9px] font-bold text-white shadow-sm"
                        >
                          CLIP
                        </span>
                      )}
                    </div>
                  </td>

                  <td className="px-3 py-3.5 max-w-xs">
                    <div className="font-medium text-gray-900 line-clamp-1">{p.nome}</div>
                    {p.descricao && (
                      <p className="text-xs text-gray-500 line-clamp-2 mt-0.5">{p.descricao}</p>
                    )}
                    {p.especificacoes_tecnicas && (
                      <span className="inline-block mt-1 text-[11px] text-gray-400 truncate max-w-full">
                        {p.especificacoes_tecnicas}
                      </span>
                    )}
                  </td>

                  <td className="px-3 py-3.5 whitespace-nowrap">
                    <span className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10">
                      {p.categoria || "Geral"}
                    </span>
                  </td>

                  <td className="px-3 py-3.5 whitespace-nowrap font-medium text-gray-600">
                    {formatCurrency(p.preco_base_fornecedor)}
                  </td>

                  <td className="px-3 py-3.5 whitespace-nowrap font-semibold text-gray-900">
                    {formatCurrency(p.preco)}
                  </td>

                  <td className="px-3 py-3.5 whitespace-nowrap">
                    {margin !== null ? (
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${
                          Number(margin) >= 30
                            ? "bg-green-100 text-green-800"
                            : Number(margin) > 0
                            ? "bg-amber-100 text-amber-800"
                            : "bg-red-100 text-red-800"
                        }`}
                      >
                        +{margin}%
                      </span>
                    ) : (
                      <span className="text-xs text-gray-400">-</span>
                    )}
                  </td>

                  <td className="py-3.5 pl-3 pr-4 text-right whitespace-nowrap">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => onEdit(p)}
                        className="rounded p-1.5 text-gray-500 hover:bg-gray-100 hover:text-blue-600 transition-colors"
                        title="Editar produto"
                      >
                        ✏️
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          if (confirm(`Deseja realmente excluir "${p.nome}"? A exclusão removerá o produto e suas fotos do catálogo visual.`)) {
                            onDelete(p.id);
                          }
                        }}
                        className="rounded p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors"
                        title="Excluir produto"
                      >
                        🗑️
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
