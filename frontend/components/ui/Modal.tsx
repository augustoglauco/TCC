"use client";

import * as Dialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export interface ModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}

/**
 * Modal genérico (não específico de RAG) sobre `@radix-ui/react-dialog` —
 * a primitiva cobre foco/Esc/teclado, a aparência é Tailwind próprio (ver
 * docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §6).
 */
export function Modal({ open, onOpenChange, title, description, children, footer }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg bg-white p-6 shadow-xl">
          <Dialog.Title className="text-lg font-semibold text-gray-900">{title}</Dialog.Title>
          {description && (
            <Dialog.Description className="mt-1 text-sm text-gray-600">
              {description}
            </Dialog.Description>
          )}
          <div className="mt-4">{children}</div>
          {footer && <div className="mt-6 flex justify-end gap-3">{footer}</div>}
          <Dialog.Close asChild>
            <button
              type="button"
              aria-label="Fechar"
              className="absolute right-4 top-4 text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
