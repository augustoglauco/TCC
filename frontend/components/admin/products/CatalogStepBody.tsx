import React from "react";
import { chaveArquivo } from "./catalogArquivos";
import type { useCatalogImport } from "./useCatalogImport";
import { CatalogUploadStep } from "./CatalogUploadStep";
import { CatalogExtractingStep } from "./CatalogExtractingStep";
import { CatalogReviewStep } from "./CatalogReviewStep";

interface CatalogStepBodyProps {
  catalog: ReturnType<typeof useCatalogImport>;
}

export function CatalogStepBody({ catalog }: CatalogStepBodyProps) {
  const { step, setFiles, setExtractedProducts } = catalog;

  if (step === "upload") {
    return (
      <CatalogUploadStep
        files={catalog.files}
        pageRange={catalog.pageRange}
        provider={catalog.provider}
        fallbackExternal={catalog.fallbackExternal}
        isDraggingOver={catalog.isDraggingOver}
        onFileChange={catalog.handleFileChange}
        onRemoveFile={(chave) => setFiles((prev) => prev.filter((f) => chaveArquivo(f) !== chave))}
        onPageRangeChange={catalog.setPageRange}
        onProviderChange={catalog.setProvider}
        onFallbackChange={catalog.setFallbackExternal}
      />
    );
  }

  if (step === "extracting") {
    return (
      <CatalogExtractingStep
        progress={catalog.progress}
        extractedCount={catalog.extractedProducts.length}
      />
    );
  }

  return (
    <CatalogReviewStep
      products={catalog.extractedProducts}
      pageErrors={catalog.pageErrors}
      onToggleSelectAll={(checked) =>
        setExtractedProducts((prev) => prev.map((item) => ({ ...item, selecionado: checked })))
      }
      onUpdateProduct={catalog.handleUpdateProduct}
      onRemoveProduct={(idTemp) =>
        setExtractedProducts((prev) => prev.filter((item) => item.id_temporario !== idTemp))
      }
      onOpenPhotoPicker={catalog.setPickerProduct}
    />
  );
}
