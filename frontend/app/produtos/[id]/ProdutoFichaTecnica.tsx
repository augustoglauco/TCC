"use client";

import React from "react";
import type { Produto } from "@/lib/api/products";

interface ProdutoFichaTecnicaProps {
  product: Produto;
}

export function ProdutoFichaTecnica({ product }: ProdutoFichaTecnicaProps) {
  return (
    <div className="mt-12 pt-8 border-t border-slate-200">
      <h2 className="text-xl font-bold text-slate-900 mb-6">Especificações e Detalhes Técnicos</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Ficha Técnica */}
        <div className="md:col-span-2 rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Ficha Técnica do Fabricante
          </h3>
          {product.especificacoes_tecnicas ? (
            <div className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">
              {product.especificacoes_tecnicas}
            </div>
          ) : (
            <p className="text-sm text-slate-400 italic">
              Especificações detalhadas não cadastradas para este produto.
            </p>
          )}
        </div>

        {/* Medidas e Metadados */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700">
            Medidas e Propriedades
          </h3>
          <div className="space-y-3 text-xs sm:text-sm">
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Dimensões (L x A x P):</span>
              <span className="font-semibold text-slate-900">
                {product.dimensoes_cm ? `${product.dimensoes_cm} cm` : "Não informado"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Peso Estimado:</span>
              <span className="font-semibold text-slate-900">
                {product.peso_kg ? `${product.peso_kg} kg` : "Não informado"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-100 pb-2">
              <span className="text-slate-500">Código do Produto:</span>
              <span className="font-mono font-semibold text-slate-900">#{product.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Categoria:</span>
              <span className="font-semibold text-slate-900">{product.categoria}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
