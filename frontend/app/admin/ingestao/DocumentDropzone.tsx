"use client";

import { useRef, useState } from "react";

const ACCEPTED_EXTENSIONS = ".txt,.md,.pdf";

interface Props {
  file: File | null;
  onFileChange: (file: File | null) => void;
  onError: (msg: string) => void;
}

function ConteudoDropzone({
  isDraggingOver,
  file,
  onRemover,
}: {
  isDraggingOver: boolean;
  file: File | null;
  onRemover: () => void;
}) {
  return (
    <>
      {isDraggingOver ? (
        <div className="space-y-1">
          <p className="text-sm font-bold text-blue-600">Solte o arquivo aqui para selecionar</p>
          <p className="text-xs text-blue-500">Formatos aceitos: .pdf, .txt, .md</p>
        </div>
      ) : file ? (
        <div className="space-y-2">
          <div className="space-y-1">
            <p className="text-sm font-bold text-slate-900">{file.name}</p>
            <p className="text-xs text-slate-500">
              {(file.size / 1024).toFixed(1)} KB — Pronto para envio
            </p>
          </div>
          <div className="flex items-center justify-center gap-3 pt-1">
            <span className="text-xs text-blue-600 font-medium hover:underline">
              Clique ou arraste outro arquivo para trocar
            </span>
            <span className="text-slate-300">|</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRemover();
              }}
              className="text-xs font-semibold text-red-600 hover:text-red-700 hover:underline cursor-pointer"
            >
              ✕ Remover
            </button>
          </div>
        </div>
      ) : (
        <div>
          <p className="text-sm font-semibold text-slate-700">
            Clique ou arraste um arquivo para selecionar
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Formatos aceitos: <span className="font-mono text-slate-700">.pdf</span>,{" "}
            <span className="font-mono text-slate-700">.txt</span>,{" "}
            <span className="font-mono text-slate-700">.md</span>
          </p>
        </div>
      )}
    </>
  );
}

export function DocumentDropzone({ file, onFileChange, onError }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.stopPropagation();
    setIsDraggingOver(false);
    const droppedFiles = e.dataTransfer.files;
    if (!droppedFiles || droppedFiles.length === 0) return;
    const droppedFile = droppedFiles[0];
    const extensao = "." + (droppedFile.name.split(".").pop() || "").toLowerCase();
    const permitidos = ACCEPTED_EXTENSIONS.split(",").map((ext) => ext.trim().toLowerCase());
    if (!permitidos.includes(extensao)) {
      onError(
        `Formato de arquivo não suportado (${extensao}). Formatos aceitos: ${ACCEPTED_EXTENSIONS}`,
      );
      return;
    }
    onFileChange(droppedFile);
  }

  return (
    <div className="space-y-2">
      <label htmlFor="file" className="block text-sm font-semibold text-slate-900">
        Arquivo
      </label>
      <div
        data-testid="document-dropzone"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        tabIndex={0}
        role="button"
        aria-label="Selecionar ou soltar arquivo para ingestão"
        className={`relative border-2 border-dashed transition-all rounded-2xl p-6 text-center space-y-2 group cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500/20 ${
          isDraggingOver
            ? "border-blue-500 bg-blue-50/80 scale-[1.01] shadow-md ring-2 ring-blue-500/30"
            : "border-slate-300 hover:border-blue-500 bg-slate-50/50 hover:bg-blue-50/30"
        }`}
      >
        <input
          ref={fileInputRef}
          id="file"
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={(e) => {
            const selected = e.target.files?.[0] ?? null;
            onFileChange(selected);
          }}
          className="sr-only"
        />
        <div
          className={`mx-auto flex h-12 w-12 items-center justify-center rounded-2xl text-2xl transition-transform ${
            isDraggingOver
              ? "bg-blue-200 text-blue-700 scale-110"
              : "bg-blue-100 text-blue-600 group-hover:scale-110"
          }`}
        >
          📄
        </div>
        <ConteudoDropzone
          isDraggingOver={isDraggingOver}
          file={file}
          onRemover={() => {
            onFileChange(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
          }}
        />
      </div>
    </div>
  );
}
