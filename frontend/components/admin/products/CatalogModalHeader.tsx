import React from "react";

interface CatalogModalHeaderProps {
  onClose: () => void;
}

export function CatalogModalHeader({ onClose }: CatalogModalHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 p-6 pb-4">
      <div>
        <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <span>📥</span> Importação Inteligente de Catálogos
        </h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Leitura página a página de PDF multipáginas, imagens ou arquivos de texto com extração via
          IA e revisão antes de salvar.
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
  );
}
