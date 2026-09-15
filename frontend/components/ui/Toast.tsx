"use client";

import { useCallback, useState } from "react";

export type ToastVariant = "success" | "error";

export interface ToastMessage {
  id: string;
  message: string;
  variant: ToastVariant;
}

/**
 * Toast genérico, sem fila global nem persistência entre páginas — estado
 * local a quem chama o hook (uma única tela administrativa, ver
 * docs/superpowers/specs/2026-09-14-registro-documentos-rag-design.md §6).
 */
export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, variant: ToastVariant = "success") => {
      const id = crypto.randomUUID();
      setToasts((current) => [...current, { id, message, variant }]);
      setTimeout(() => dismissToast(id), 4000);
    },
    [dismissToast],
  );

  return { toasts, showToast, dismissToast };
}

export function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className={`rounded-md px-4 py-3 text-sm shadow-lg ${
            toast.variant === "success" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-800"
          }`}
        >
          <div className="flex items-center gap-3">
            <span>{toast.message}</span>
            <button
              type="button"
              aria-label="Fechar aviso"
              onClick={() => onDismiss(toast.id)}
              className="text-current opacity-60 hover:opacity-100"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
