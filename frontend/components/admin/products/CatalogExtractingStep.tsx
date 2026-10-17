"use client";

import type { CatalogExtractionProgress } from "@/lib/types/adminProducts";

interface CatalogExtractingStepProps {
  progress: CatalogExtractionProgress;
  extractedCount: number;
}

export function CatalogExtractingStep({ progress, extractedCount }: CatalogExtractingStepProps) {
  return (
    <div className="py-12 flex flex-col items-center justify-center text-center space-y-4">
      <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
      <div>
        <h3 className="text-lg font-bold text-gray-900">
          Lendo catálogo e identificando produtos...
        </h3>
        <p className="text-sm text-gray-500 mt-1 max-w-md">
          {progress.status || "Processando páginas..."}
        </p>
      </div>

      {progress.total > 0 && (
        <div className="w-full max-w-md mt-4">
          <div className="flex justify-between text-xs font-semibold text-gray-600 mb-1">
            <span>
              Página {progress.pagina} de {progress.total}
            </span>
            <span>{Math.round((progress.pagina / progress.total) * 100)}%</span>
          </div>
          <div className="h-2 w-full rounded-full bg-gray-200 overflow-hidden">
            <div
              className="h-full bg-blue-600 transition-all duration-300 rounded-full"
              style={{
                width: `${Math.min(100, Math.round((progress.pagina / progress.total) * 100))}%`,
              }}
            />
          </div>
        </div>
      )}

      <div className="text-xs text-blue-600 font-medium">
        {extractedCount} produto(s) identificado(s) até o momento...
      </div>
    </div>
  );
}
