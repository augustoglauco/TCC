"use client";

import { useRef } from "react";

import { FileTypeIcon } from "@/components/ui/FileTypeIcon";

const ACCEPTED_EXTENSIONS = ".pdf,.md,.txt";

interface Props {
  file: File | null;
  onFileChange: (file: File | null) => void;
}

/** Campo opcional do arquivo que o cliente baixa no chat (ex.: o PDF original do `.md` tratado).
 * Só é guardado, nunca indexado: o texto buscado vem do arquivo principal. */
export function DownloadFileInput({ file, onFileChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-2">
      <label htmlFor="download-file" className="block text-sm font-semibold text-slate-900">
        Arquivo para download (opcional)
      </label>
      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50/50 p-3">
        {file ? <FileTypeIcon filename={file.name} className="h-10 w-8 shrink-0" /> : null}
        <input
          ref={inputRef}
          id="download-file"
          type="file"
          accept={ACCEPTED_EXTENSIONS}
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          className="min-w-0 flex-1 text-xs text-slate-700 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-100 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-blue-700 hover:file:bg-blue-200"
        />
        {file ? (
          <button
            type="button"
            onClick={() => {
              onFileChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="text-xs font-semibold text-red-600 hover:text-red-700 hover:underline cursor-pointer"
          >
            ✕ Remover
          </button>
        ) : null}
      </div>
      <p className="text-xs text-slate-500">
        É o arquivo que o cliente baixa no chat no lugar do enviado acima (por exemplo, o PDF
        original do fornecedor, enquanto o .md tratado é o que a busca lê). Não é indexado.
      </p>
    </div>
  );
}
