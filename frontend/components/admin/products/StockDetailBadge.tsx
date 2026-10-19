"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useEstaNoCliente } from "@/lib/hooks/useEstaNoCliente";
import type { AdminProductStock } from "@/lib/types/adminProducts";

interface StockDetailBadgeProps {
  totalEstoque: number;
  estoques?: AdminProductStock[];
}

interface TooltipCoords {
  top: number;
  left: number;
  placeBelow: boolean;
}

const BUBBLE_ESTIMATED_HEIGHT = 130;

function rectEstaZerado(rect: DOMRect): boolean {
  return rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0;
}

function calcularCoords(rect: DOMRect): TooltipCoords | null {
  if (rectEstaZerado(rect)) return null;
  const placeBelow = rect.top < BUBBLE_ESTIMATED_HEIGHT;
  return {
    top: placeBelow ? rect.bottom + 8 : rect.top - 8,
    left: rect.left + rect.width / 2,
    placeBelow,
  };
}

function estiloFixo(coords: TooltipCoords | null): React.CSSProperties | undefined {
  if (!coords) return undefined;
  return {
    position: "fixed",
    top: coords.placeBelow ? `${coords.top}px` : undefined,
    bottom: !coords.placeBelow ? `${window.innerHeight - coords.top}px` : undefined,
    left: `${coords.left}px`,
    transform: "translateX(-50%)",
  };
}

function StockTooltipLista({
  estoques,
  totalEstoque,
}: {
  estoques: AdminProductStock[];
  totalEstoque: number;
}) {
  return (
    <div className="space-y-1.5">
      {estoques.map((est, idx) => (
        <div
          key={est.id || `${est.centro_distribuicao}-${idx}`}
          className="flex items-center justify-between"
        >
          <span
            className="text-slate-300 font-medium truncate max-w-[130px]"
            title={est.centro_distribuicao}
          >
            {est.centro_distribuicao}
          </span>
          <span className="font-semibold text-emerald-400 bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
            {est.quantidade} un
          </span>
        </div>
      ))}
      <div className="border-t border-slate-800 pt-1.5 mt-2 flex items-center justify-between font-semibold text-slate-200">
        <span>Total no estoque:</span>
        <span className="text-emerald-300">{totalEstoque} un</span>
      </div>
    </div>
  );
}

function StockTooltip({
  coords,
  estoques,
  totalEstoque,
}: {
  coords: TooltipCoords | null;
  estoques?: AdminProductStock[];
  totalEstoque: number;
}) {
  const posicao = coords ? "z-[9999]" : "absolute top-full left-0 z-[100]";
  const temEstoque = Boolean(estoques && estoques.length > 0);
  return (
    <div
      role="tooltip"
      style={estiloFixo(coords)}
      className={`${posicao} pointer-events-none w-56 rounded-xl border border-slate-700 bg-slate-900 p-3 text-xs text-slate-100 shadow-2xl animate-in fade-in-50 duration-150`}
    >
      <div className="flex items-center gap-1.5 border-b border-slate-800 pb-2 mb-2 font-semibold text-slate-200">
        <span>📦</span>
        <span>Detalhamento por CD</span>
      </div>

      {temEstoque ? (
        <StockTooltipLista estoques={estoques!} totalEstoque={totalEstoque} />
      ) : (
        <p className="text-slate-400 italic">Nenhum CD com estoque registrado.</p>
      )}
    </div>
  );
}

function useTooltipCoords(isOpen: boolean) {
  const badgeRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<TooltipCoords | null>(null);

  const updatePosition = useCallback(() => {
    if (!badgeRef.current) return;
    setCoords(calcularCoords(badgeRef.current.getBoundingClientRect()));
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

  return { badgeRef, coords, updatePosition };
}

export default function StockDetailBadge({ totalEstoque, estoques }: StockDetailBadgeProps) {
  const [isOpen, setIsOpen] = useState(false);
  const mounted = useEstaNoCliente();
  const { badgeRef, coords, updatePosition } = useTooltipCoords(isOpen);

  const bubbleElement = isOpen ? (
    <StockTooltip coords={coords} estoques={estoques} totalEstoque={totalEstoque} />
  ) : null;
  const corBadge =
    totalEstoque > 0
      ? "bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100"
      : "bg-gray-100 text-gray-600 border border-gray-200 hover:bg-gray-200";

  return (
    <>
      <span
        ref={badgeRef}
        onMouseEnter={() => {
          updatePosition();
          setIsOpen(true);
        }}
        onMouseLeave={() => setIsOpen(false)}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium cursor-help transition-all ${corBadge}`}
      >
        <span>📦</span>
        <span>{totalEstoque} un</span>
      </span>
      {mounted && typeof document !== "undefined" && bubbleElement
        ? createPortal(bubbleElement, document.body)
        : bubbleElement}
    </>
  );
}
