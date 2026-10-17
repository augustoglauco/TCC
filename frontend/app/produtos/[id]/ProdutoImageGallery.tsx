"use client";

import React from "react";

interface ProdutoImageGalleryProps {
  imageList: string[];
  currentImgIndex: number;
  productName: string;
  onSelectIndex: (idx: number) => void;
  onZoom: (url: string) => void;
}

export function ProdutoImageGallery({
  imageList,
  currentImgIndex,
  productName,
  onSelectIndex,
  onZoom,
}: ProdutoImageGalleryProps) {
  const activeImageUrl = imageList[currentImgIndex] || null;

  return (
    <div className="space-y-4">
      <div className="relative aspect-4/3 w-full overflow-hidden rounded-2xl border border-slate-200/80 bg-white p-4 flex items-center justify-center shadow-xs group">
        {activeImageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={activeImageUrl}
            alt={productName}
            className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105 cursor-pointer"
            onClick={() => onZoom(activeImageUrl)}
          />
        ) : (
          <div className="flex flex-col items-center justify-center text-slate-400 p-8 text-center">
            <svg
              className="h-16 w-16 text-slate-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
            <span className="mt-2 text-xs text-slate-400">Sem foto disponível</span>
          </div>
        )}

        {activeImageUrl && (
          <button
            type="button"
            onClick={() => onZoom(activeImageUrl)}
            className="absolute top-3 right-3 rounded-full bg-slate-900/60 p-2 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-slate-900 cursor-pointer"
            title="Ampliar imagem (Zoom)"
            aria-label="Ampliar imagem"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
              />
            </svg>
          </button>
        )}

        {imageList.length > 1 && (
          <>
            <button
              type="button"
              onClick={() =>
                onSelectIndex(currentImgIndex === 0 ? imageList.length - 1 : currentImgIndex - 1)
              }
              className="absolute left-2.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1.5 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
              aria-label="Imagem anterior"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>

            <button
              type="button"
              onClick={() =>
                onSelectIndex(currentImgIndex === imageList.length - 1 ? 0 : currentImgIndex + 1)
              }
              className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1.5 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
              aria-label="Próxima imagem"
            >
              <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2.5}
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </>
        )}
      </div>

      {imageList.length > 1 && (
        <div className="flex gap-2.5 overflow-x-auto pb-2">
          {imageList.map((url, idx) => (
            <button
              type="button"
              key={url}
              onClick={() => onSelectIndex(idx)}
              className={`relative h-18 w-18 shrink-0 overflow-hidden rounded-xl border p-1 transition-all cursor-pointer ${
                currentImgIndex === idx
                  ? "border-blue-600 ring-2 ring-blue-600/30"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
              aria-label={`Ver foto ${idx + 1}`}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={url}
                alt={`Foto ${idx + 1}`}
                className="h-full w-full object-contain rounded-lg"
              />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
