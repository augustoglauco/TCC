"use client";

import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export type ModalSize = "sm" | "md" | "lg" | "xl" | "2xl" | "3xl";

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  headerActions?: ReactNode;
  size?: ModalSize;
}

const SIZE_CLASSES: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-xl",
  "2xl": "max-w-2xl",
  "3xl": "max-w-3xl",
};

/**
 * Modal genérico sobre `@radix-ui/react-dialog`.
 * Suporta tamanhos customizados (`size`), fundo translúcido (glassmorphism) e design moderno.
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  headerActions,
  size = "md",
}: ModalProps) {
  const sizeClass = SIZE_CLASSES[size] || SIZE_CLASSES.md;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs transition-opacity duration-200" />
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 z-50 w-[calc(100vw-1.5rem)] sm:w-full ${sizeClass} max-h-[92vh] flex flex-col -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-slate-200/80 bg-white p-3.5 sm:p-5 shadow-2xl transition-all duration-200 overflow-y-auto`}
        >
          <div className="flex items-center justify-between gap-2.5 sm:gap-4 border-b border-slate-100 pb-3 shrink-0">
            <div className="flex flex-col min-w-0">
              <Dialog.Title asChild>
                <div className="text-base sm:text-lg font-bold text-slate-900 truncate flex items-center gap-2">
                  {title}
                </div>
              </Dialog.Title>
              {description && (
                <Dialog.Description className="mt-0.5 text-xs text-slate-500 truncate hidden sm:block">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
              {headerActions}
              <Dialog.Close asChild>
                <button
                  type="button"
                  aria-label="Fechar"
                  className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-all hover:scale-105 active:scale-95 shrink-0"
                >
                  ✕
                </button>
              </Dialog.Close>
            </div>
          </div>

          <div className="mt-3 sm:mt-4 flex-1 min-h-0 flex flex-col">{children}</div>

          {footer && (
            <div className="mt-4 sm:mt-6 flex justify-end gap-3 border-t border-slate-100 pt-3 sm:pt-4 shrink-0">
              {footer}
            </div>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
