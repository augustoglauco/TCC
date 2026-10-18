"use client";

import { useState } from "react";

import { fileToBase64 } from "@/lib/utils/fileToBase64";

interface UseChatDropZoneParams {
  disabled: boolean;
  onImage: (base64: string, name: string) => void;
  onAudio: (base64: string) => void;
  onError: (text: string) => void;
}

/** Arrastar-e-soltar de imagem ou áudio sobre a área do chat. */
export function useChatDropZone({ disabled, onImage, onAudio, onError }: UseChatDropZoneParams) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (!isDraggingOver) setIsDraggingOver(true);
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDraggingOver(false);
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);

    if (disabled) return;

    const file = e.dataTransfer.files?.[0];
    if (!file) return;

    const isImage = file.type.startsWith("image/");
    const isAudio =
      file.type.startsWith("audio/") || /\.(mp3|wav|m4a|ogg|webm|aac|flac)$/i.test(file.name);

    try {
      if (isImage) {
        onImage(await fileToBase64(file), file.name);
      } else if (isAudio) {
        onAudio(await fileToBase64(file));
      } else {
        onError(
          "Formato de arquivo não suportado. Por favor, envie imagens (PNG, JPG, WEBP) ou áudios.",
        );
      }
    } catch {
      onError("Erro ao processar o arquivo arrastado. Tente novamente.");
    }
  }

  return { isDraggingOver, handleDragOver, handleDragLeave, handleDrop };
}
