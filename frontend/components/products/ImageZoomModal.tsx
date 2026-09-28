"use client";

import { useEffect, useState } from "react";

interface ImageZoomModalProps {
  imageUrl: string;
  productName: string;
  onClose: () => void;
}

export function ImageZoomModal({ imageUrl, productName, onClose }: ImageZoomModalProps) {
  const [zoomLevel, setZoomLevel] = useState(1);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleZoomIn = () => setZoomLevel((prev) => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoomLevel((prev) => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => setZoomLevel(1);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-in fade-in duration-200">
      {/* Botão Fechar no canto superior direito */}
      <button
        type="button"
        onClick={onClose}
        className="absolute top-4 right-4 z-10 rounded-full bg-white/20 p-2 text-white hover:bg-white/40 focus:outline-none transition-colors cursor-pointer"
        aria-label="Fechar visualização de imagem"
      >
        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>

      {/* Painel de Controles de Zoom */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 rounded-full bg-slate-900/80 px-4 py-2 text-white shadow-lg backdrop-blur-md">
        <button
          type="button"
          onClick={handleZoomOut}
          className="rounded p-1 hover:bg-white/20 transition-colors cursor-pointer"
          title="Diminuir Zoom (-)"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>

        <span className="text-xs font-mono w-14 text-center select-none">
          {Math.round(zoomLevel * 100)}%
        </span>

        <button
          type="button"
          onClick={handleZoomIn}
          className="rounded p-1 hover:bg-white/20 transition-colors cursor-pointer"
          title="Aumentar Zoom (+)"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>

        <div className="h-4 w-px bg-white/20 mx-1" />

        <button
          type="button"
          onClick={handleResetZoom}
          className="text-xs font-medium hover:text-blue-300 transition-colors cursor-pointer px-1"
        >
          Resetar
        </button>
      </div>

      {/* Container de exibição da imagem */}
      <div className="max-h-[85vh] max-w-[90vw] overflow-auto flex items-center justify-center p-4">
        {/* eslint-disable-next-html-element-suppression */}
        <img
          src={imageUrl}
          alt={productName}
          style={{ transform: `scale(${zoomLevel})` }}
          className="max-h-[75vh] max-w-full object-contain transition-transform duration-200 select-none shadow-2xl rounded"
        />
      </div>

      {/* Legenda/Nome do Produto */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 z-10 rounded-lg bg-slate-900/80 px-4 py-2 text-sm font-medium text-white max-w-md truncate text-center shadow-lg backdrop-blur-md">
        {productName}
      </div>
    </div>
  );
}
