"use client";

import React from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import type { ExtractedProductItem } from "@/lib/types/adminProducts";

interface CatalogPhotoPickerProps {
  product: ExtractedProductItem;
  uploading: boolean;
  onSelectPhoto: (url: string) => void;
  onRemovePhoto: () => void;
  onUploadPhoto: (file: File) => void;
  onClose: () => void;
}

export function CatalogPhotoPicker({
  product,
  uploading,
  onSelectPhoto,
  onRemovePhoto,
  onUploadPhoto,
  onClose,
}: CatalogPhotoPickerProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
      <div className="relative w-full max-w-lg rounded-xl bg-white p-5 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b pb-3 border-gray-100">
          <div>
            <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
              <span>🖼️</span> Selecionar Foto do Produto
            </h3>
            <p className="text-xs text-gray-500 truncate max-w-sm mt-0.5">{product.nome}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <div className="flex items-center gap-4 bg-gray-50 p-3 rounded-lg border border-gray-200">
          <div className="h-16 w-16 rounded border bg-white overflow-hidden flex items-center justify-center shrink-0">
            {product.imagem_temp_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={
                  product.imagem_temp_url.startsWith("http")
                    ? product.imagem_temp_url
                    : `${getApiBaseUrl()}${product.imagem_temp_url}`
                }
                alt="Foto selecionada"
                className="h-full w-full object-contain p-1"
              />
            ) : (
              <span className="text-xs text-gray-400 text-center">Sem foto</span>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold text-gray-700">Foto Atual</div>
            <div className="text-[11px] text-gray-500">
              {product.imagem_temp_url
                ? "Figura recortada associada ao produto"
                : "Nenhuma foto selecionada"}
            </div>
          </div>
          {product.imagem_temp_url && (
            <button
              type="button"
              onClick={onRemovePhoto}
              className="text-xs text-red-600 hover:text-red-800 font-semibold px-2 py-1 rounded hover:bg-red-50"
            >
              Remover Foto
            </button>
          )}
        </div>

        <div>
          <label className="block text-xs font-bold text-gray-700 mb-1.5">
            Fotos Detectadas no Catálogo (Página {product.pagina_origem || 1})
          </label>
          {product.fotos_pagina && product.fotos_pagina.length > 0 ? (
            <div className="grid grid-cols-4 sm:grid-cols-5 gap-2 max-h-48 overflow-y-auto p-1 bg-gray-50/50 rounded-lg border border-gray-200">
              {product.fotos_pagina.map((fotoUrl, fIdx) => {
                const isSelected = product.imagem_temp_url === fotoUrl;
                return (
                  <button
                    key={fIdx}
                    type="button"
                    onClick={() => onSelectPhoto(fotoUrl)}
                    className={`relative aspect-square rounded-lg border-2 bg-white overflow-hidden p-1 flex items-center justify-center hover:opacity-90 transition-all ${
                      isSelected
                        ? "border-blue-600 ring-2 ring-blue-400"
                        : "border-gray-200 hover:border-gray-400"
                    }`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={fotoUrl.startsWith("http") ? fotoUrl : `${getApiBaseUrl()}${fotoUrl}`}
                      alt={`Figura ${fIdx + 1}`}
                      className="h-full w-full object-contain"
                    />
                    {isSelected && (
                      <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] text-white font-bold">
                        ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="text-xs text-gray-500 italic p-3 bg-gray-50 rounded-lg text-center">
              Nenhuma figura individual foi identificada nesta página.
            </div>
          )}
        </div>

        <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
          <div>
            <input
              type="file"
              accept="image/*"
              id="picker-upload-file"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  onUploadPhoto(e.target.files[0]);
                }
              }}
            />
            <label
              htmlFor="picker-upload-file"
              className="cursor-pointer inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 hover:bg-blue-100"
            >
              <span>📁</span> {uploading ? "Enviando..." : "Enviar Foto do Computador"}
            </label>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-gray-800"
          >
            Concluir
          </button>
        </div>
      </div>
    </div>
  );
}
