"use client";

import { useRef } from "react";

export interface ImageUploaderProps {
  disabled?: boolean;
  onImageSelected: (imageBase64: string, fileName: string) => void;
}

const ACCEPTED = "image/png,image/jpeg,image/webp";

/** Converte um File para base64 (sem o prefixo data:…;base64,). */
async function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // Remove o prefixo "data:<mime>;base64,"
      resolve(result.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(new Error("Falha ao ler o arquivo."));
    reader.readAsDataURL(file);
  });
}

export default function ImageUploader({ disabled, onImageSelected }: ImageUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    // Reseta o input para permitir selecionar o mesmo arquivo novamente.
    e.target.value = "";
    const base64 = await fileToBase64(file);
    onImageSelected(base64, file.name);
  }

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="sr-only"
        aria-label="Enviar imagem"
        onChange={handleChange}
        disabled={disabled}
      />
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        title="Enviar imagem (PNG, JPG ou WEBP)"
        className="rounded-xl border border-slate-300 bg-slate-50 px-3 py-2.5 text-slate-600 hover:bg-slate-100 disabled:opacity-50 transition-colors"
        aria-label="Enviar imagem"
      >
        🖼️
      </button>
    </>
  );
}
