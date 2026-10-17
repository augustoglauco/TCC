"use client";

import React from "react";

type ModalStep = "upload" | "extracting" | "review";

interface CatalogFooterActionsProps {
  step: ModalStep;
  filesCount: number;
  selectedCount: number;
  totalCount: number;
  saving: boolean;
  onClose: () => void;
  onStartExtraction: () => void;
  onBackToUpload: () => void;
  onConfirmBatch: () => void;
}

export function CatalogFooterActions({
  step,
  filesCount,
  selectedCount,
  totalCount,
  saving,
  onClose,
  onStartExtraction,
  onBackToUpload,
  onConfirmBatch,
}: CatalogFooterActionsProps) {
  return (
    <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-6 py-4">
      <div>
        {step === "review" && (
          <span className="text-xs font-semibold text-gray-700">
            {selectedCount} de {totalCount} produto(s) selecionados para gravação
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        {step === "upload" && (
          <>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={onStartExtraction}
              disabled={filesCount === 0}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              Iniciar Extração Inteligente
            </button>
          </>
        )}

        {step === "review" && (
          <>
            <button
              type="button"
              onClick={onBackToUpload}
              disabled={saving}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
            >
              ← Voltar
            </button>
            <button
              type="button"
              onClick={onConfirmBatch}
              disabled={saving || selectedCount === 0}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
            >
              {saving
                ? "Gravando e Vetorizando no CLIP..."
                : `Confirmar e Gravar ${selectedCount} Produto(s)`}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
