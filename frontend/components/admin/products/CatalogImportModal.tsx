"use client";

import React, { useState } from "react";
import { chaveArquivo } from "./catalogArquivos";
import { useCatalogImport } from "./useCatalogImport";
import { CatalogUploadStep } from "./CatalogUploadStep";
import { CatalogExtractingStep } from "./CatalogExtractingStep";
import { CatalogReviewStep } from "./CatalogReviewStep";
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
  const {
    step,
    setStep,
    files,
    setFiles,
    pageRange,
    setPageRange,
    provider,
    setProvider,
    fallbackExternal,
    setFallbackExternal,
    isDraggingOver,
    progress,
    extractedProducts,
    setExtractedProducts,
    saving,
    error,
    pageErrors,
    pickerProduct,
    setPickerProduct,
    uploadingPickerPhoto,
    selectedCount,
    handleFileChange,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleStartExtraction,
    handleUpdateProduct,
    handleConfirmBatch,
    pickerHandlers,
  } = useCatalogImport({ isOpen, onClose, onSuccess });

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <CatalogDragDropZone
        isDraggingOver={isDraggingOver}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center justify-between border-b border-gray-100 p-6 pb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <span>📥</span> Importação Inteligente de Catálogos
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Leitura página a página de PDF multipáginas, imagens ou arquivos de texto com extração
              via IA e revisão antes de salvar.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div className="flex-1 overflow-y-auto p-6 pt-2">
          {step === "upload" && (
            <CatalogUploadStep
              files={files}
              pageRange={pageRange}
              provider={provider}
              fallbackExternal={fallbackExternal}
              isDraggingOver={isDraggingOver}
              onFileChange={handleFileChange}
              onRemoveFile={(chave) =>
                setFiles((prev) => prev.filter((f) => chaveArquivo(f) !== chave))
              }
              onPageRangeChange={setPageRange}
              onProviderChange={setProvider}
              onFallbackChange={setFallbackExternal}
            />
          )}

          {step === "extracting" && (
            <CatalogExtractingStep progress={progress} extractedCount={extractedProducts.length} />
          )}

          {step === "review" && (
            <CatalogReviewStep
              products={extractedProducts}
              pageErrors={pageErrors}
              onToggleSelectAll={(checked) =>
                setExtractedProducts((prev) =>
                  prev.map((item) => ({ ...item, selecionado: checked })),
                )
              }
              onUpdateProduct={handleUpdateProduct}
              onRemoveProduct={(idTemp) =>
                setExtractedProducts((prev) => prev.filter((item) => item.id_temporario !== idTemp))
              }
              onOpenPhotoPicker={setPickerProduct}
            />
          )}
        </div>

        <CatalogFooterActions
          step={step}
          filesCount={files.length}
          selectedCount={selectedCount}
          totalCount={extractedProducts.length}
          saving={saving}
          onClose={onClose}
          onStartExtraction={handleStartExtraction}
          onBackToUpload={() => setStep("upload")}
          onConfirmBatch={handleConfirmBatch}
        />

        {pickerProduct && (
          <CatalogPhotoPicker
            product={pickerProduct}
            uploading={uploadingPickerPhoto}
            onSelectPhoto={pickerHandlers.select}
            onRemovePhoto={pickerHandlers.remove}
            onUploadPhoto={pickerHandlers.upload}
            onClose={() => setPickerProduct(null)}
          />
        )}
      </CatalogDragDropZone>
    </div>
  );
}
