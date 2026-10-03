"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { RagCollection } from "@/lib/types/rag";

export interface CollectionOptionCardProps {
  collection: RagCollection;
  isSelected: boolean;
  onToggle: (id: string) => void;
}

export function CollectionOptionCard({
  collection,
  isSelected,
  onToggle,
}: CollectionOptionCardProps) {
  const [mounted, setMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const cardRef = useRef<HTMLLabelElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number; placeBelow: boolean } | null>(
    null,
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  const updatePosition = useCallback(() => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) {
      setCoords(null);
      return;
    }

    const bubbleWidth = 320;
    const bubbleEstimatedHeight = 280;
    const viewportWidth = window.innerWidth || 1024;

    const spaceAbove = rect.top;
    const placeBelow = spaceAbove < bubbleEstimatedHeight + 16;

    let left = rect.left + rect.width / 2;
    // Garante que o centro do bubble não extrapole as bordas laterais
    left = Math.max(bubbleWidth / 2 + 12, Math.min(left, viewportWidth - bubbleWidth / 2 - 12));

    setCoords({
      top: placeBelow ? rect.bottom + 8 : rect.top - 8,
      left,
      placeBelow,
    });
  }, []);

  useEffect(() => {
    if (isOpen) {
      updatePosition();
      window.addEventListener("scroll", updatePosition, true);
      window.addEventListener("resize", updatePosition);
      return () => {
        window.removeEventListener("scroll", updatePosition, true);
        window.removeEventListener("resize", updatePosition);
      };
    }
  }, [isOpen, updatePosition]);

  const handleMouseEnter = () => {
    updatePosition();
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    setIsOpen(false);
  };

  const bubbleContent = (
    <div
      role="tooltip"
      id={`bubble-collection-${collection.id}`}
      style={
        coords
          ? {
              position: "fixed",
              top: coords.placeBelow ? `${coords.top}px` : undefined,
              bottom: !coords.placeBelow ? `${window.innerHeight - coords.top}px` : undefined,
              left: `${coords.left}px`,
              transform: "translateX(-50%)",
            }
          : undefined
      }
      className={`${
        coords ? "z-[9999]" : "absolute top-full left-0 z-[100]"
      } pointer-events-none w-76 sm:w-80 rounded-2xl border border-slate-700/80 bg-slate-900 p-4 text-xs text-slate-100 shadow-2xl animate-in fade-in-50 duration-150 space-y-3`}
    >
      {/* Topo: Nome, Status e Purpose */}
      <div className="flex items-start justify-between gap-2 border-b border-slate-800 pb-2.5">
        <div className="min-w-0">
          <span className="font-bold text-sm text-white block truncate">{collection.name}</span>
          <span className="text-[10px] text-slate-400 font-mono">ID: {collection.id}</span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
              collection.is_active
                ? "bg-emerald-950 text-emerald-300 border border-emerald-800/60"
                : "bg-slate-800 text-slate-400 border border-slate-700"
            }`}
          >
            {collection.is_active ? "Ativa" : "Inativa"}
          </span>
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-950 text-blue-300 border border-blue-800/60">
            {collection.purpose}
          </span>
        </div>
      </div>

      {/* Destaque: Quantidade de Arquivos Indexados */}
      <div className="flex items-center justify-between rounded-xl bg-slate-800/90 border border-slate-700/60 p-2.5">
        <div className="flex items-center gap-2">
          <span className="text-base">📁</span>
          <span className="font-semibold text-slate-200">Arquivos indexados:</span>
        </div>
        <span className="font-bold text-emerald-400 text-sm bg-emerald-950/80 px-2 py-0.5 rounded-md border border-emerald-800/40">
          {collection.document_count ?? 0} {collection.document_count === 1 ? "documento" : "documentos"}
        </span>
      </div>

      {/* Parâmetros de Vetorização */}
      <div className="space-y-1">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
          Vetorização & Embeddings
        </span>
        <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-300 bg-slate-800/40 p-2 rounded-lg border border-slate-800">
          <div className="col-span-2 truncate">
            <span className="text-slate-400">Modelo: </span>
            <span className="font-mono text-white text-[10px]">{collection.embedding_model}</span>
          </div>
          <div>
            <span className="text-slate-400">Dimensão: </span>
            <span className="font-semibold text-slate-200">{collection.vector_dimension}</span>
          </div>
          <div>
            <span className="text-slate-400">Métrica: </span>
            <span className="font-semibold text-slate-200 uppercase">{collection.distance_metric}</span>
          </div>
        </div>
      </div>

      {/* Parâmetros de Chunking */}
      <div className="space-y-1">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
          Configuração de Chunking
        </span>
        <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-300 bg-slate-800/40 p-2 rounded-lg border border-slate-800">
          <div>
            <span className="text-slate-400">Chunk Size: </span>
            <span className="font-semibold text-slate-200">{collection.chunk_size} tokens</span>
          </div>
          <div>
            <span className="text-slate-400">Overlap: </span>
            <span className="font-semibold text-slate-200">{collection.chunk_overlap} tokens</span>
          </div>
        </div>
      </div>

      {/* Parâmetros HNSW & Armazenamento */}
      <div className="space-y-1">
        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
          HNSW, Quantização & Índices
        </span>
        <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-300 bg-slate-800/40 p-2 rounded-lg border border-slate-800">
          <div>
            <span className="text-slate-400">HNSW M / ef: </span>
            <span className="font-mono text-slate-200">
              {collection.hnsw_m} / {collection.hnsw_ef_construct}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Armazenamento: </span>
            <span className="font-semibold text-slate-200">
              {collection.hnsw_on_disk ? "Em Disco" : "Em RAM"}
            </span>
          </div>
          <div>
            <span className="text-slate-400">Quantização: </span>
            <span className="font-mono text-slate-200 uppercase">{collection.quantization_type}</span>
          </div>
          <div>
            <span className="text-slate-400">Payload Índices: </span>
            <span className="font-semibold text-slate-200">
              {collection.payload_indexes?.length ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* Rodapé: Data */}
      {collection.created_at && (
        <div className="border-t border-slate-800 pt-2 flex items-center justify-between text-[10px] text-slate-400">
          <span>Criada em:</span>
          <span>{new Date(collection.created_at).toLocaleDateString("pt-BR")}</span>
        </div>
      )}
    </div>
  );

  return (
    <>
      <label
        ref={cardRef}
        htmlFor={`col-${collection.id}`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocus={handleMouseEnter}
        onBlur={handleMouseLeave}
        className={`group flex items-start justify-between gap-3 rounded-xl border p-3 cursor-pointer transition-all relative ${
          isSelected
            ? "border-blue-500 bg-blue-50/50 shadow-2xs ring-1 ring-blue-500/20"
            : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/40"
        }`}
      >
        <div className="flex items-start gap-2.5 min-w-0">
          <input
            type="checkbox"
            id={`col-${collection.id}`}
            aria-label={collection.name}
            checked={isSelected}
            onChange={() => onToggle(collection.id)}
            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
          />
          <div className="min-w-0">
            <span className="font-semibold text-xs text-slate-900 block truncate">
              {collection.name}
            </span>
            <span className="text-[10px] text-slate-400 font-mono block truncate">
              dim: {collection.vector_dimension} • chunk: {collection.chunk_size} • {collection.document_count ?? 0} docs
            </span>
          </div>
        </div>

        <span
          className={`text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0 ${
            collection.is_active
              ? "bg-emerald-100/80 text-emerald-800"
              : "bg-slate-100 text-slate-500"
          }`}
        >
          {collection.is_active ? "Ativa" : "Inativa"}
        </span>
      </label>

      {isOpen && mounted && typeof document !== "undefined"
        ? createPortal(bubbleContent, document.body)
        : null}
    </>
  );
}
