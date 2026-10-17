"use client";

import React from "react";

interface ProductCardImageProps {
  imageList: string[];
  currentImgIndex: number;
  productName: string;
  onZoom: (url: string) => void;
  onPrev: (e: React.MouseEvent) => void;
  onNext: (e: React.MouseEvent) => void;
}

export function ProductCardImage({
  imageList,
  currentImgIndex,
  productName,
  onZoom,
  onPrev,
  onNext,
}: ProductCardImageProps) {
  const activeImageUrl = imageList[currentImgIndex] || null;

  return (
    <div className="relative mt-4 aspect-4/3 w-full overflow-hidden rounded-xl bg-slate-50 flex items-center justify-center group/img border border-slate-100">
      {activeImageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={activeImageUrl}
          alt={productName}
          className="h-full w-full object-contain p-3 transition-transform duration-300 group-hover/img:scale-105 cursor-pointer"
          onClick={() => onZoom(activeImageUrl)}
        />
      ) : (
        <div className="flex flex-col items-center justify-center text-slate-400 p-4 text-center">
          <svg
            className="h-10 w-10 text-slate-300"
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
          <span className="mt-1 text-xs text-slate-400">Sem foto cadastrada</span>
        </div>
      )}

      {activeImageUrl && (
        <button
          type="button"
          onClick={() => onZoom(activeImageUrl)}
          className="absolute top-2 right-2 rounded-full bg-slate-900/70 p-2 text-white opacity-90 sm:opacity-0 sm:group-hover/img:opacity-100 transition-opacity hover:bg-slate-900 cursor-pointer"
          title="Ampliar imagem (Zoom)"
          aria-label="Ampliar imagem"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
            onClick={onPrev}
            className="absolute left-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
            aria-label="Imagem anterior"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
            onClick={onNext}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-full bg-slate-900/60 p-1 text-white hover:bg-slate-900 transition-all cursor-pointer opacity-80 hover:opacity-100"
            aria-label="Próxima imagem"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2.5}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>

          <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 rounded-full bg-slate-900/70 px-2 py-0.5 text-[10px] text-white">
            {currentImgIndex + 1} / {imageList.length}
          </div>
        </>
      )}
    </div>
  );
}
