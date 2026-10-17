"use client";

import React from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import { CatalogPriceInput } from "./CatalogImportModal";
import type { ExtractedProductItem } from "@/lib/types/adminProducts";

interface CatalogReviewStepProps {
  products: ExtractedProductItem[];
  pageErrors: string[];
  onToggleSelectAll: (checked: boolean) => void;
  onUpdateProduct: (
    idTemp: string | undefined,
    field: keyof ExtractedProductItem,
    value: ExtractedProductItem[keyof ExtractedProductItem],
  ) => void;
  onRemoveProduct: (idTemp: string | undefined) => void;
  onOpenPhotoPicker: (item: ExtractedProductItem) => void;
}

export function CatalogReviewStep({
  products,
  pageErrors,
  onToggleSelectAll,
  onUpdateProduct,
  onRemoveProduct,
  onOpenPhotoPicker,
}: CatalogReviewStepProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between bg-blue-50 p-3 rounded-lg border border-blue-100">
        <div className="text-xs text-blue-900">
          <strong>Conferência Prévia:</strong> Revise os dados extraídos, ajuste nomes e preços ou
          desmarque produtos que não deseja incluir.
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onToggleSelectAll(true)}
            className="text-xs text-blue-700 font-semibold underline hover:text-blue-900"
          >
            Marcar Todos
          </button>
          <span className="text-gray-300">|</span>
          <button
            type="button"
            onClick={() => onToggleSelectAll(false)}
            className="text-xs text-blue-700 font-semibold underline hover:text-blue-900"
          >
            Desmarcar Todos
          </button>
        </div>
      </div>

      {pageErrors.length > 0 && (
        <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
          <p className="font-semibold mb-1">
            {products.length === 0
              ? "Não foi possível extrair produtos — houve falha ao processar:"
              : "Algumas páginas falharam durante a extração:"}
          </p>
          <ul className="list-disc list-inside space-y-0.5">
            {pageErrors.map((msg, idx) => (
              <li key={idx}>{msg}</li>
            ))}
          </ul>
        </div>
      )}

      {products.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm">
          {pageErrors.length === 0
            ? "Nenhum produto foi detectado nos arquivos fornecidos."
            : "Nenhum produto foi extraído — corrija o problema acima e tente novamente."}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="bg-gray-50 text-gray-500 font-semibold uppercase tracking-wider border-b border-gray-200">
                <th className="p-3 w-8">Sel.</th>
                <th className="p-3 w-16">Foto</th>
                <th className="p-3">Nome do Produto</th>
                <th className="p-3 w-32">Categoria</th>
                <th className="p-3 w-32">Preço Revend.</th>
                <th className="p-3 w-32">Preço Venda</th>
                <th className="p-3">Descrição / Specs</th>
                <th className="p-3 w-10 text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {products.map((item) => (
                <tr
                  key={item.id_temporario}
                  className={item.selecionado ? "hover:bg-blue-50/20" : "opacity-50 bg-gray-50"}
                >
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={Boolean(item.selecionado)}
                      onChange={(e) =>
                        onUpdateProduct(item.id_temporario, "selecionado", e.target.checked)
                      }
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </td>
                  <td className="p-3">
                    <div className="flex flex-col items-center gap-1">
                      <button
                        type="button"
                        onClick={() => onOpenPhotoPicker(item)}
                        title="Clique para trocar a foto ou escolher outra da página"
                        className="group relative h-12 w-12 rounded-lg border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center hover:border-blue-500 hover:ring-2 hover:ring-blue-200 transition-all cursor-pointer"
                      >
                        {item.imagem_temp_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={
                              item.imagem_temp_url.startsWith("http")
                                ? item.imagem_temp_url
                                : `${getApiBaseUrl()}${item.imagem_temp_url}`
                            }
                            alt="Preview"
                            className="h-full w-full object-contain p-0.5"
                          />
                        ) : (
                          <span className="text-gray-400 group-hover:scale-110 transition-transform">
                            📷
                          </span>
                        )}
                        <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-[10px] font-bold transition-opacity">
                          Trocar
                        </div>
                      </button>
                      {item.fotos_pagina && item.fotos_pagina.length > 1 && (
                        <button
                          type="button"
                          onClick={() => onOpenPhotoPicker(item)}
                          className="text-[10px] text-blue-600 hover:text-blue-800 font-medium underline"
                        >
                          {item.fotos_pagina.length} fotos
                        </button>
                      )}
                    </div>
                  </td>
                  <td className="p-3">
                    <input
                      type="text"
                      value={item.nome}
                      onChange={(e) => onUpdateProduct(item.id_temporario, "nome", e.target.value)}
                      className="w-full rounded border border-gray-300 px-2 py-1 font-medium text-gray-900 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="p-3">
                    <input
                      type="text"
                      value={item.categoria || ""}
                      onChange={(e) =>
                        onUpdateProduct(item.id_temporario, "categoria", e.target.value)
                      }
                      className="w-full rounded border border-gray-300 px-2 py-1 text-gray-700 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="p-3">
                    <CatalogPriceInput
                      value={item.preco_base_fornecedor}
                      onChange={(val) =>
                        onUpdateProduct(item.id_temporario, "preco_base_fornecedor", val)
                      }
                      ariaLabel={`Preço revenda ${item.nome}`}
                    />
                  </td>
                  <td className="p-3">
                    <CatalogPriceInput
                      value={item.preco}
                      onChange={(val) => onUpdateProduct(item.id_temporario, "preco", val)}
                      isBold
                      ariaLabel={`Preço venda ${item.nome}`}
                    />
                  </td>
                  <td className="p-3">
                    <input
                      type="text"
                      value={item.descricao || item.especificacoes_tecnicas || ""}
                      onChange={(e) =>
                        onUpdateProduct(item.id_temporario, "descricao", e.target.value)
                      }
                      className="w-full rounded border border-gray-300 px-2 py-1 text-gray-600 focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="p-3 text-right">
                    <button
                      type="button"
                      onClick={() => onRemoveProduct(item.id_temporario)}
                      title="Descartar item"
                      className="text-gray-400 hover:text-red-600"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
