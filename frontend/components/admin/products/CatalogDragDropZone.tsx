"use client";

import React from "react";

interface CatalogDragDropZoneProps {
  isDraggingOver: boolean;
  onDragOver: (e: React.DragEvent<HTMLDivElement>) => void;
  onDragLeave: (e: React.DragEvent<HTMLDivElement>) => void;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  children: React.ReactNode;
}

export function CatalogDragDropZone({
  isDraggingOver,
  onDragOver,
  onDragLeave,
  onDrop,
  children,
}: CatalogDragDropZoneProps) {
  return (
    <div
      className={`relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden transition-all ${
        isDraggingOver ? "ring-4 ring-blue-400 ring-offset-2" : ""
      }`}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {children}
    </div>
  );
}
