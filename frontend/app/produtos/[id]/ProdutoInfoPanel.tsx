"use client";

import React from "react";
import type { Produto } from "@/lib/api/products";

interface ProdutoInfoPanelProps {
  product: Produto;
  emEstoque: boolean;
  totalEstoque: number;
  onBuy: () => void;
  onQuote: () => void;
}

function valorFormatado(val: number): string {
  return `R$ ${val.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function EstoquePorCd({ estoques }: { estoques: Produto["estoques"] }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-slate-50/70 p-4 space-y-2.5">
      <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
        <span>📍</span> Disponibilidade por Centro de Distribuição
      </h2>
      {estoques && estoques.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {estoques.map((est) => (
            <div
              key={est.id}
              className="rounded-xl border border-slate-200 bg-white p-2.5 text-xs shadow-2xs"
            >
              <span className="block font-semibold text-slate-700 truncate">
                {est.centro_distribuicao}
              </span>
              <span
                className={`block font-bold mt-0.5 ${
                  est.quantidade > 0 ? "text-emerald-700" : "text-slate-400"
                }`}
              >
                {est.quantidade > 0 ? `${est.quantidade} un` : "Esgotado"}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">Nenhum estoque registrado para este item.</p>
      )}
    </div>
  );
}

function DescontosVolume({ descontos }: { descontos: Produto["descontos_volume"] }) {
  return (
    <>
      {descontos && descontos.length > 0 && (
        <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-4 space-y-2">
          <h2 className="text-xs font-bold uppercase tracking-wider text-blue-900 flex items-center gap-2">
            <span>🏷️</span> Tabela de Descontos Progressivos
          </h2>
          <div className="flex flex-wrap gap-2">
            {descontos.map((desc) => (
              <span
                key={desc.id}
                className="inline-flex items-center gap-1 rounded-lg border border-blue-200 bg-white px-2.5 py-1 text-xs font-semibold text-blue-800"
              >
                A partir de {desc.quantidade_minima} un:{" "}
                <strong className="text-blue-600">{Number(desc.percentual_desconto)}% OFF</strong>
              </span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

export function ProdutoInfoPanel({
  product,
  emEstoque,
  totalEstoque,
  onBuy,
  onQuote,
}: ProdutoInfoPanelProps) {
  return (
    <div className="flex flex-col justify-between space-y-6">
      <div className="space-y-4">
        {/* Categoria e Badge de Estoque */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="rounded-md bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
            {product.categoria}
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              emEstoque
                ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                : "bg-amber-50 text-amber-700 border border-amber-200"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${emEstoque ? "bg-emerald-500" : "bg-amber-500"}`}
            />
            {emEstoque ? `Em estoque (${totalEstoque} un)` : "Sem estoque no momento"}
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 leading-tight">
          {product.nome}
        </h1>

        {product.descricao && (
          <p className="text-sm text-slate-600 leading-relaxed">{product.descricao}</p>
        )}

        {/* Preço */}
        <div className="pt-2">
          <span className="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Preço Unitário
          </span>
          <div className="flex items-baseline gap-3">
            {product.preco_promocional ? (
              <>
                <span className="text-3xl font-extrabold text-blue-700">
                  {valorFormatado(product.preco_promocional)}
                </span>
                <span className="text-sm text-slate-400 line-through">
                  {valorFormatado(product.preco)}
                </span>
                <span className="rounded-md bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 text-xs font-bold">
                  Oferta Especial
                </span>
              </>
            ) : (
              <span className="text-3xl font-extrabold text-blue-700">
                {valorFormatado(product.preco)}
              </span>
            )}
          </div>
        </div>

        {/* Botões de Ação */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-4 border-t border-slate-100">
          <button
            type="button"
            onClick={onBuy}
            disabled={!emEstoque}
            className={`flex items-center justify-center gap-2 rounded-xl py-3 px-4 text-sm font-bold shadow-xs transition-all cursor-pointer ${
              emEstoque
                ? "bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow"
                : "bg-slate-200 text-slate-400 cursor-not-allowed"
            }`}
          >
            <span>🛒</span>
            <span>Comprar Agora</span>
          </button>

          <button
            type="button"
            onClick={onQuote}
            className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white py-3 px-4 text-sm font-semibold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300 transition-colors shadow-xs cursor-pointer"
          >
            <span>💬</span>
            <span>Cotar com Assistente</span>
          </button>
        </div>
      </div>

      <EstoquePorCd estoques={product.estoques} />

      <DescontosVolume descontos={product.descontos_volume} />
    </div>
  );
}
