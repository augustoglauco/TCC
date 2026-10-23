"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { RagCollection } from "@/lib/types/rag";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";

export interface CollectionOptionCardProps {
  collection: RagCollection;
  isSelected: boolean;
  onToggle: (id: string) => void;
}

type Coords = { top: number; left: number; placeBelow: boolean };

const BUBBLE_WIDTH = 320;
const BUBBLE_ESTIMATED_HEIGHT = 280;

function calcularCoords(rect: DOMRect): Coords | null {
  if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) return null;

  const viewportWidth = window.innerWidth || 1024;
  const placeBelow = rect.top < BUBBLE_ESTIMATED_HEIGHT + 16;

  // Garante que o centro do bubble não extrapole as bordas laterais
  const left = Math.max(
    BUBBLE_WIDTH / 2 + 12,
    Math.min(rect.left + rect.width / 2, viewportWidth - BUBBLE_WIDTH / 2 - 12),
  );

  return { top: placeBelow ? rect.bottom + 8 : rect.top - 8, left, placeBelow };
}

function estiloPosicionado(coords: Coords | null): React.CSSProperties | undefined {
  if (!coords) return undefined;
  return {
    position: "fixed",
    top: coords.placeBelow ? `${coords.top}px` : undefined,
    bottom: !coords.placeBelow ? `${window.innerHeight - coords.top}px` : undefined,
    left: `${coords.left}px`,
    transform: "translateX(-50%)",
  };
}

function Secao({ titulo, children }: { titulo: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">
        {titulo}
      </span>
      <div className="grid grid-cols-2 gap-1.5 text-[11px] text-slate-300 bg-slate-800/40 p-2 rounded-lg border border-slate-800">
        {children}
      </div>
    </div>
  );
}

function Campo({
  rotulo,
  valorClass,
  className,
  children,
}: {
  rotulo: string;
  valorClass: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={className}>
      <span className="text-slate-400">{rotulo}: </span>
      <span className={valorClass}>{children}</span>
    </div>
  );
}

function BubbleTopo({ collection }: { collection: RagCollection }) {
  return (
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
  );
}

function BubbleArquivos({ collection }: { collection: RagCollection }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-slate-800/90 border border-slate-700/60 p-2.5">
      <div className="flex items-center gap-2">
        <span className="text-base">📁</span>
        <span className="font-semibold text-slate-200">Arquivos indexados:</span>
      </div>
      <span className="font-bold text-emerald-400 text-sm bg-emerald-950/80 px-2 py-0.5 rounded-md border border-emerald-800/40">
        {collection.document_count ?? 0}{" "}
        {collection.document_count === 1 ? "documento" : "documentos"}
      </span>
    </div>
  );
}

const VALOR = "font-semibold text-slate-200";
const VALOR_MONO = "font-mono text-slate-200";

function BubbleParametros({ collection }: { collection: RagCollection }) {
  return (
    <>
      <Secao titulo="Vetorização &amp; Embeddings">
        <Campo
          rotulo="Modelo"
          className="col-span-2 truncate"
          valorClass="font-mono text-white text-[10px]"
        >
          {collection.embedding_model}
        </Campo>
        <Campo rotulo="Dimensão" valorClass={VALOR}>
          {collection.vector_dimension}
        </Campo>
        <Campo rotulo="Métrica" valorClass={`${VALOR} uppercase`}>
          {collection.distance_metric}
        </Campo>
      </Secao>

      <Secao titulo="Configuração de Chunking">
        <Campo rotulo="Chunk Size" valorClass={VALOR}>
          {collection.chunk_size} tokens
        </Campo>
        <Campo rotulo="Overlap" valorClass={VALOR}>
          {collection.chunk_overlap} tokens
        </Campo>
      </Secao>

      <Secao titulo="HNSW, Quantização &amp; Índices">
        <Campo rotulo="HNSW M / ef" valorClass={VALOR_MONO}>
          {collection.hnsw_m} / {collection.hnsw_ef_construct}
        </Campo>
        <Campo rotulo="Armazenamento" valorClass={VALOR}>
          {collection.hnsw_on_disk ? "Em Disco" : "Em RAM"}
        </Campo>
        <Campo rotulo="Quantização" valorClass={`${VALOR_MONO} uppercase`}>
          {collection.quantization_type}
        </Campo>
        <Campo rotulo="Payload Índices" valorClass={VALOR}>
          {collection.payload_indexes?.length ?? 0}
        </Campo>
      </Secao>
    </>
  );
}

function CollectionBubble({
  collection,
  coords,
}: {
  collection: RagCollection;
  coords: Coords | null;
}) {
  return (
    <div
      role="tooltip"
      id={`bubble-collection-${collection.id}`}
      style={estiloPosicionado(coords)}
      className={`${
        coords ? "z-[9999]" : "absolute top-full left-0 z-[100]"
      } pointer-events-none w-76 sm:w-80 rounded-2xl border border-slate-700/80 bg-slate-900 p-4 text-xs text-slate-100 shadow-2xl animate-in fade-in-50 duration-150 space-y-3`}
    >
      <BubbleTopo collection={collection} />
      <BubbleArquivos collection={collection} />
      <BubbleParametros collection={collection} />
      {collection.created_at && (
        <div className="border-t border-slate-800 pt-2 flex items-center justify-between text-[10px] text-slate-400">
          <span>Criada em:</span>
          <span>{new Date(collection.created_at).toLocaleDateString("pt-BR")}</span>
        </div>
      )}
    </div>
  );
}

export function CollectionOptionCard({
  collection,
  isSelected,
  onToggle,
}: CollectionOptionCardProps) {
  const mounted = useEstaNoCliente();
  const [isOpen, setIsOpen] = useState(false);
  const cardRef = useRef<HTMLLabelElement>(null);
  const [coords, setCoords] = useState<Coords | null>(null);

  const updatePosition = useCallback(() => {
    if (!cardRef.current) return;
    setCoords(calcularCoords(cardRef.current.getBoundingClientRect()));
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    updatePosition();
    window.addEventListener("scroll", updatePosition, true);
    window.addEventListener("resize", updatePosition);
    return () => {
      window.removeEventListener("scroll", updatePosition, true);
      window.removeEventListener("resize", updatePosition);
    };
  }, [isOpen, updatePosition]);

  const handleMouseEnter = () => {
    updatePosition();
    setIsOpen(true);
  };

  const handleMouseLeave = () => {
    setIsOpen(false);
  };

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
              dim: {collection.vector_dimension} • chunk: {collection.chunk_size} •{" "}
              {collection.document_count ?? 0} docs
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
        ? createPortal(<CollectionBubble collection={collection} coords={coords} />, document.body)
        : null}
    </>
  );
}
