"use client";

import {
  cloneElement,
  isValidElement,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactElement,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";

// Detecta "estamos no cliente" sem `useState`+`useEffect` — useSyncExternalStore
// é o jeito recomendado pelo React para esse caso específico (retorna o
// snapshot do servidor até hidratar, depois o do cliente, sem o setState
// síncrono dentro de efeito que o hook set-state-in-effect reclamaria).
function subscribeNoop() {
  return () => {};
}
function useEstaNoCliente(): boolean {
  return useSyncExternalStore(
    subscribeNoop,
    () => true,
    () => false,
  );
}

export type TooltipPosition = "top" | "bottom" | "left" | "right" | "auto";
export type TooltipAlign = "start" | "center" | "end" | "auto";

export interface TooltipProps {
  content: string;
  ariaLabel?: string;
  position?: TooltipPosition;
  align?: TooltipAlign;
  /** Elemento customizado que dispara o tooltip no hover/foco, no lugar do
   * botão "?" padrão — usado quando o gatilho precisa ser um elemento que
   * já tem seus próprios filhos interativos (ex.: um card inteiro com
   * botões dentro, que não podem ficar aninhados num <button>). Os
   * handlers de hover/foco já existentes no elemento passado continuam
   * sendo chamados (não são sobrescritos). */
  trigger?: ReactElement;
  /** Conteúdo rico (JSX) do corpo do tooltip, no lugar do texto simples de
   * `content`. `content` continua sendo usado para o `aria-label` padrão
   * do botão "?" quando `trigger` não é usado. */
  renderContent?: () => ReactNode;
}

/**
 * Componente de Tooltip acessível e inteligente para formulários, modais e
 * cards administrativos. Utiliza Portal do React e posicionamento fixo
 * dinâmico para garantir que o tooltip NUNCA seja cortado por contêineres
 * com scroll (`overflow-y-auto`) ou bordas de modais, ajustando seu
 * alinhamento à esquerda/direita.
 */
export function Tooltip({
  content,
  ariaLabel,
  position = "auto",
  align = "auto",
  trigger,
  renderContent,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const mounted = useEstaNoCliente();
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);
  const tooltipWidth = renderContent ? 288 : 240; // w-72 vs w-60
  // Timeout de ocultar com um pequeno atraso (ver `agendarEsconder` abaixo)
  // — permite o cursor atravessar o gap de 6px entre o gatilho e o corpo do
  // tooltip (posicionado `rect.bottom + 6`) sem fechar o painel no meio do
  // caminho (achado #2 da revisão final: o botão de refresh dentro do
  // painel ficava inalcançável nos cards com `trigger`/hover).
  const esconderTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateCoords = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    // Em ambientes sem layout (como jsdom), rect pode retornar zeros
    if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) {
      setCoords(null);
      return;
    }

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
      } else if (rect.left > viewportWidth - tooltipWidth - 20) {
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
    if (
      position === "top" ||
      (position === "auto" && rect.bottom + tooltipEstimatedHeight > viewportHeight)
    ) {
      top = Math.max(12, rect.top - tooltipEstimatedHeight - 6);
    }

    setCoords({ top, left });
  }, [align, position, tooltipWidth]);

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
  }, [isVisible, updateCoords]);

  const mostrar = useCallback(() => {
    if (esconderTimeoutRef.current) {
      clearTimeout(esconderTimeoutRef.current);
      esconderTimeoutRef.current = null;
    }
    setIsVisible(true);
  }, []);
  // Esconde imediatamente (sem atraso) — usado no `onBlur`, que não tem o
  // problema do gap de mouse a atravessar.
  const esconder = useCallback(() => setIsVisible(false), []);
  // Atraso curto antes de esconder (em vez de síncrono) — dá tempo do
  // cursor atravessar o gap de 6px entre o gatilho e o corpo do tooltip
  // (posicionado `rect.bottom + 6`) sem que o `onMouseLeave` do gatilho já
  // tenha desmontado o painel no caminho (achado #2 da revisão final: o
  // botão de refresh dentro do painel ficava inalcançável nos cards com
  // `trigger`/hover).
  const agendarEsconder = useCallback(() => {
    esconderTimeoutRef.current = setTimeout(() => {
      setIsVisible(false);
      esconderTimeoutRef.current = null;
    }, 150);
  }, []);

  const tooltipBody = renderContent ? renderContent() : content;
  const classeCorpo = renderContent
    ? "w-72 rounded-xl border border-slate-200 bg-white p-3 text-xs font-normal leading-relaxed text-slate-900 shadow-2xl pointer-events-auto text-left animate-in fade-in-50 duration-150"
    : "w-60 rounded-xl border border-slate-700 bg-slate-900 p-2.5 text-xs font-normal leading-relaxed text-slate-100 shadow-2xl pointer-events-none text-left animate-in fade-in-50 duration-150";

  const tooltipElement = isVisible ? (
    <span
      ref={tooltipRef}
      role="tooltip"
      // Também dispara mostrar/agendar-esconder ao entrar/sair do próprio
      // corpo do tooltip — sem isso, mover o cursor do gatilho até o painel
      // (trigger) dispara `mouseleave` no gatilho e desmonta o painel antes
      // do cursor chegar nele (achado #2 da revisão final). Inofensivo no
      // tooltip simples (`pointer-events-none`): o mouse não interage com
      // ele de qualquer forma.
      onMouseEnter={mostrar}
      onMouseLeave={agendarEsconder}
      style={
        coords
          ? {
              position: "fixed",
              top: `${coords.top}px`,
              left: `${coords.left}px`,
            }
          : undefined
      }
      className={
        coords
          ? `z-[9999] ${classeCorpo}`
          : `absolute top-full left-0 mt-1.5 z-[100] ${classeCorpo}`
      }
    >
      {tooltipBody}
    </span>
  ) : null;

  const tooltipPortal =
    mounted && typeof document !== "undefined"
      ? createPortal(tooltipElement, document.body)
      : tooltipElement;

  if (trigger) {
    const triggerClonado = isValidElement(trigger)
      ? // cloneElement repassando `ref` pro elemento host é o padrão
        // intencional de forwarding aqui, não um acesso a ref durante o
        // render que a regra deveria pegar (falso positivo).
        // eslint-disable-next-line react-hooks/refs
        cloneElement(trigger, {
          ref: triggerRef,
          onMouseEnter: (e: React.MouseEvent) => {
            (trigger.props as { onMouseEnter?: (e: React.MouseEvent) => void }).onMouseEnter?.(e);
            mostrar();
          },
          onMouseLeave: (e: React.MouseEvent) => {
            (trigger.props as { onMouseLeave?: (e: React.MouseEvent) => void }).onMouseLeave?.(e);
            agendarEsconder();
          },
          onFocus: (e: React.FocusEvent) => {
            (trigger.props as { onFocus?: (e: React.FocusEvent) => void }).onFocus?.(e);
            mostrar();
          },
          onBlur: (e: React.FocusEvent) => {
            (trigger.props as { onBlur?: (e: React.FocusEvent) => void }).onBlur?.(e);
            esconder();
          },
        } as Partial<unknown>)
      : trigger;

    return (
      <>
        {triggerClonado}
        {tooltipPortal}
      </>
    );
  }

  return (
    <span className="relative inline-flex items-center">
      <button
        ref={triggerRef as React.RefObject<HTMLButtonElement>}
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
      {tooltipPortal}
    </span>
  );
}
