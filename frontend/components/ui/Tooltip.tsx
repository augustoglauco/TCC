"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type TooltipPosition = "top" | "bottom" | "left" | "right" | "auto";
export type TooltipAlign = "start" | "center" | "end" | "auto";

export interface TooltipProps {
  content: string;
  ariaLabel?: string;
  position?: TooltipPosition;
  align?: TooltipAlign;
}

/**
 * Componente de Tooltip acessível e inteligente para formulários e modais.
 * Utiliza Portal do React e posicionamento fixo dinâmico para garantir que
 * o tooltip NUNCA seja cortado por contêineres com scroll (`overflow-y-auto`)
 * ou bordas de modais, ajustando seu alinhamento à esquerda/direita.
 */
export function Tooltip({
  content,
  ariaLabel,
  position = "auto",
  align = "auto",
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [mounted, setMounted] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const updateCoords = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    // Em ambientes sem layout (como jsdom), rect pode retornar zeros
    if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) {
      setCoords(null);
      return;
    }

    const tooltipWidth = 240; // w-60 = 240px
    const tooltipEstimatedHeight = 110;
    const viewportWidth = window.innerWidth || 1024;
    const viewportHeight = window.innerHeight || 768;

    let left = rect.left;

    if (align === "center") {
      left = rect.left + rect.width / 2 - tooltipWidth / 2;
    } else if (align === "end") {
      left = rect.right - tooltipWidth;
    } else if (align === "start") {
      left = rect.left;
    } else {
      // align === "auto"
      // Se o gatilho estiver próximo da borda esquerda, alinha à esquerda do gatilho
      if (rect.left < 200) {
        left = Math.max(16, rect.left - 4);
      } else if (rect.left > viewportWidth - 260) {
        // Se estiver próximo da borda direita, alinha à direita
        left = rect.right - tooltipWidth;
      } else {
        // Caso intermediário: levemente recuado à esquerda em relação ao gatilho
        left = rect.left - 16;
      }
    }

    // Limita estritamente dentro da viewport (com margem de 16px das bordas da tela)
    left = Math.max(16, Math.min(left, viewportWidth - tooltipWidth - 16));

    let top = rect.bottom + 6;
    if (position === "top" || (position === "auto" && rect.bottom + tooltipEstimatedHeight > viewportHeight)) {
      top = Math.max(12, rect.top - tooltipEstimatedHeight - 6);
    }

    setCoords({ top, left });
  };

  useEffect(() => {
    if (isVisible) {
      updateCoords();
      window.addEventListener("scroll", updateCoords, true);
      window.addEventListener("resize", updateCoords);
      return () => {
        window.removeEventListener("scroll", updateCoords, true);
        window.removeEventListener("resize", updateCoords);
      };
    }
  }, [isVisible, align, position]);

  const tooltipElement = isVisible ? (
    <span
      ref={tooltipRef}
      role="tooltip"
      style={
        coords
          ? {
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
            }
          : undefined
      }
      className={`${
        coords ? "z-[9999]" : "absolute top-full left-0 mt-1.5 z-[100]"
      } w-60 rounded-xl border border-slate-700 bg-slate-900 p-2.5 text-xs font-normal leading-relaxed text-slate-100 shadow-2xl pointer-events-none text-left animate-in fade-in-50 duration-150`}
    >
      {content}
    </span>
  ) : null;

  return (
    <span className="relative inline-flex items-center">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsVisible((prev) => !prev)}
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
        onFocus={() => setIsVisible(true)}
        onBlur={() => setIsVisible(false)}
        aria-label={ariaLabel || `Dica: ${content}`}
        className="ml-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-slate-200/80 text-[10px] font-bold text-slate-600 transition-all hover:bg-blue-600 hover:text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
      >
        ?
      </button>
      {mounted && typeof document !== "undefined"
        ? createPortal(tooltipElement, document.body)
        : tooltipElement}
    </span>
  );
}

