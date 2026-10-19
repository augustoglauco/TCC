"use client";

import React, { useState } from "react";
import { useCatalogImport } from "./useCatalogImport";
import { CatalogModalHeader } from "./CatalogModalHeader";
import { CatalogStepBody } from "./CatalogStepBody";
import { CatalogPhotoPicker } from "./CatalogPhotoPicker";
import { CatalogDragDropZone } from "./CatalogDragDropZone";
import { CatalogFooterActions } from "./CatalogFooterActions";

interface CatalogImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// ─── Utilitários de moeda (exportados para uso em testes e CatalogReviewStep) ─

interface CatalogPriceInputProps {
  value: number | null | undefined;
  onChange: (val: number | null) => void;
  isBold?: boolean;
  ariaLabel?: string;
}

export function formatarMoedaInput(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || isNaN(valor)) return "";
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function parseMoedaInput(texto: string): number | null {
  const limpo = texto.trim().replace(/[^\d,.-]/g, "");
  if (!limpo) return null;
  let normalizado = limpo;
  if (normalizado.includes(",") && normalizado.includes(".")) {
    normalizado = normalizado.replace(/\./g, "").replace(",", ".");
  } else if (normalizado.includes(",")) {
    normalizado = normalizado.replace(",", ".");
  }
  const num = parseFloat(normalizado);
  return isNaN(num) ? null : Number(num.toFixed(2));
}

export function CatalogPriceInput({
  value,
  onChange,
  isBold = false,
  ariaLabel,
}: CatalogPriceInputProps) {
  const [texto, setTexto] = useState(() => formatarMoedaInput(value));
  const [focado, setFocado] = useState(false);

  const [valueAnterior, setValueAnterior] = useState(value);
  if (value !== valueAnterior && !focado) {
    setValueAnterior(value);
    setTexto(formatarMoedaInput(value));
  }

  const handleBlur = () => {
    setFocado(false);
    const parsed = parseMoedaInput(texto);
    onChange(parsed);
    setTexto(formatarMoedaInput(parsed));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const novoTexto = e.target.value;
    setTexto(novoTexto);
    onChange(parseMoedaInput(novoTexto));
  };

  return (
    <div className="relative flex items-center rounded border border-gray-300 bg-white transition-colors focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 shadow-2xs">
      <span className="pl-2 pr-0.5 text-[11px] font-semibold text-gray-500 select-none">R$</span>
      <input
        type="text"
        inputMode="decimal"
        value={texto}
        onChange={handleChange}
        onFocus={(e) => {
          setFocado(true);
          e.target.select();
        }}
        onBlur={handleBlur}
        placeholder="0,00"
        aria-label={ariaLabel}
        className={`w-full bg-transparent px-1.5 py-1 text-right text-xs focus:outline-none ${
          isBold ? "font-bold text-gray-900" : "font-medium text-gray-700"
        }`}
      />
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function CatalogImportModal({
  isOpen,
  onClose,
  onSuccess,
}: CatalogImportModalProps) {
  const catalog = useCatalogImport({ isOpen, onClose, onSuccess });
  const { pickerProduct, pickerHandlers } = catalog;

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <CatalogDragDropZone
        isDraggingOver={catalog.isDraggingOver}
        onDragOver={catalog.handleDragOver}
        onDragLeave={catalog.handleDragLeave}
        onDrop={catalog.handleDrop}
      >
        <CatalogModalHeader onClose={onClose} />

        {catalog.error && (
          <div className="mx-6 mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {catalog.error}
          </div>
        )}

        <div className="flex-1 overflow-y-auto p-6 pt-2">
          <CatalogStepBody catalog={catalog} />
        </div>

        <CatalogFooterActions
          step={catalog.step}
          filesCount={catalog.files.length}
          selectedCount={catalog.selectedCount}
          totalCount={catalog.extractedProducts.length}
          saving={catalog.saving}
          onClose={onClose}
          onStartExtraction={catalog.handleStartExtraction}
          onBackToUpload={() => catalog.setStep("upload")}
          onConfirmBatch={catalog.handleConfirmBatch}
        />

        {pickerProduct && (
          <CatalogPhotoPicker
            product={pickerProduct}
            uploading={catalog.uploadingPickerPhoto}
            onSelectPhoto={pickerHandlers.select}
            onRemovePhoto={pickerHandlers.remove}
            onUploadPhoto={pickerHandlers.upload}
            onClose={() => catalog.setPickerProduct(null)}
          />
        )}
      </CatalogDragDropZone>
    </div>
  );
}
