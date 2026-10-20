"use client";

import React from "react";
import type { RagCollection, RagDomain } from "@/lib/types/rag";

const DOMAIN_OPTIONS: { value: RagDomain; label: string }[] = [
  { value: "vendas", label: "Vendas" },
  { value: "suporte", label: "Suporte Técnico" },
  { value: "atendimento", label: "Atendimento ao Usuário" },
];

interface DocumentsFilterBarProps {
  filtroNome: string;
  dominiosSelecionados: RagDomain[];
  collectionIdSelecionada: string;
  dataInicio: string;
  dataFim: string;
  collections: RagCollection[];
  totalDocumentos: number;
  totalFiltrados: number;
  temFiltroAtivo: boolean;
  onFiltroNome: (v: string) => void;
  onToggleDomain: (d: RagDomain) => void;
  onCollectionChange: (v: string) => void;
  onDataInicio: (v: string) => void;
  onDataFim: (v: string) => void;
  onLimpar: () => void;
}

function RangeDatas({
  dataInicio,
  dataFim,
  onDataInicio,
  onDataFim,
}: {
  dataInicio: string;
  dataFim: string;
  onDataInicio: (v: string) => void;
  onDataFim: (v: string) => void;
}) {
  return (
    <div className="md:col-span-5 space-y-1">
      <span className="block text-xs font-semibold text-slate-700 uppercase tracking-wider">
        Range de data
      </span>
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-1.5">
          <label
            htmlFor="filtro-data-inicio"
            className="text-xs text-slate-500 font-medium shrink-0"
          >
            De:
          </label>
          <input
            id="filtro-data-inicio"
            aria-label="De:"
            type="date"
            value={dataInicio}
            onChange={(e) => onDataInicio(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white py-1.5 px-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
        <div className="flex-1 flex items-center gap-1.5">
          <label htmlFor="filtro-data-fim" className="text-xs text-slate-500 font-medium shrink-0">
            Até:
          </label>
          <input
            id="filtro-data-fim"
            aria-label="Até:"
            type="date"
            value={dataFim}
            onChange={(e) => onDataFim(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white py-1.5 px-2 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>
    </div>
  );
}

function LinhaInferior({
  dominiosSelecionados,
  totalDocumentos,
  totalFiltrados,
  temFiltroAtivo,
  onToggleDomain,
  onLimpar,
}: {
  dominiosSelecionados: RagDomain[];
  totalDocumentos: number;
  totalFiltrados: number;
  temFiltroAtivo: boolean;
  onToggleDomain: (d: RagDomain) => void;
  onLimpar: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-200/60">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs font-semibold text-slate-600 mr-1">Domínios:</span>
        {DOMAIN_OPTIONS.map((opt) => {
          const isSelected = dominiosSelecionados.includes(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onToggleDomain(opt.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
                isSelected
                  ? "bg-blue-600 text-white shadow-xs ring-2 ring-blue-600/30"
                  : "bg-white text-slate-700 border border-slate-200 hover:bg-slate-100"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3 ml-auto">
        <span className="text-xs text-slate-500">
          Exibindo <span className="font-semibold text-slate-800">{totalFiltrados}</span> de{" "}
          <span className="font-semibold text-slate-800">{totalDocumentos}</span> documentos
        </span>
        {temFiltroAtivo && (
          <button
            type="button"
            onClick={onLimpar}
            className="text-xs font-semibold text-blue-600 hover:text-blue-800 underline transition-colors"
          >
            Limpar filtros
          </button>
        )}
      </div>
    </div>
  );
}

export function DocumentsFilterBar({
  filtroNome,
  dominiosSelecionados,
  collectionIdSelecionada,
  dataInicio,
  dataFim,
  collections,
  totalDocumentos,
  totalFiltrados,
  temFiltroAtivo,
  onFiltroNome,
  onToggleDomain,
  onCollectionChange,
  onDataInicio,
  onDataFim,
  onLimpar,
}: DocumentsFilterBarProps) {
  return (
    <div className="mb-5 rounded-2xl border border-slate-200/80 bg-slate-50/60 p-4 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
        {/* Nome do arquivo */}
        <div className="md:col-span-4 space-y-1">
          <label
            htmlFor="filtro-nome"
            className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
          >
            Nome do arquivo
          </label>
          <div className="relative">
            <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 text-xs">
              🔍
            </span>
            <input
              id="filtro-nome"
              type="text"
              value={filtroNome}
              onChange={(e) => onFiltroNome(e.target.value)}
              placeholder="Buscar por nome do arquivo..."
              className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        {/* Collection */}
        <div className="md:col-span-3 space-y-1">
          <label
            htmlFor="filtro-collection"
            className="block text-xs font-semibold text-slate-700 uppercase tracking-wider"
          >
            Collection
          </label>
          <select
            id="filtro-collection"
            aria-label="Collection"
            value={collectionIdSelecionada}
            onChange={(e) => onCollectionChange(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white py-2 px-3 text-xs text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">Todas as collections</option>
            {collections.map((col) => (
              <option key={col.id} value={col.id}>
                {col.name} {col.is_active ? "(Ativa)" : ""}
              </option>
            ))}
          </select>
        </div>

        {/* Range de data */}
        <RangeDatas
          dataInicio={dataInicio}
          dataFim={dataFim}
          onDataInicio={onDataInicio}
          onDataFim={onDataFim}
        />
      </div>

      <LinhaInferior
        dominiosSelecionados={dominiosSelecionados}
        totalDocumentos={totalDocumentos}
        totalFiltrados={totalFiltrados}
        temFiltroAtivo={temFiltroAtivo}
        onToggleDomain={onToggleDomain}
        onLimpar={onLimpar}
      />
    </div>
  );
}
