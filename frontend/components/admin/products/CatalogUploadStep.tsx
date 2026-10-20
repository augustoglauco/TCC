"use client";

import React from "react";
function chaveArquivo(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}`;
}

interface CatalogUploadStepProps {
  files: File[];
  pageRange: string;
  provider: "local" | "external";
  fallbackExternal: boolean;
  isDraggingOver: boolean;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoveFile: (chave: string) => void;
  onPageRangeChange: (v: string) => void;
  onProviderChange: (v: "local" | "external") => void;
  onFallbackChange: (v: boolean) => void;
}

function OpcaoProvider({
  valor,
  selecionado,
  titulo,
  descricao,
  onChange,
}: {
  valor: "local" | "external";
  selecionado: boolean;
  titulo: string;
  descricao: string;
  onChange: (v: "local" | "external") => void;
}) {
  return (
    <label
      className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-all ${
        selecionado
          ? "border-blue-600 bg-blue-50/40 ring-1 ring-blue-600"
          : "border-gray-200 hover:bg-gray-50"
      }`}
    >
      <input
        type="radio"
        name="provider"
        value={valor}
        checked={selecionado}
        onChange={() => onChange(valor)}
        className="mt-1 text-blue-600"
      />
      <div>
        <span className="block text-sm font-semibold text-gray-900">{titulo}</span>
        <span className="block text-xs text-gray-500 mt-0.5">{descricao}</span>
      </div>
    </label>
  );
}

function IntervaloPaginas({
  pageRange,
  onChange,
}: {
  pageRange: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-2">
      <div className="flex items-center justify-between">
        <label
          htmlFor="page-range-input"
          className="block text-xs font-bold uppercase tracking-wider text-gray-700"
        >
          Intervalo de Páginas do PDF (opcional)
        </label>
        <span className="text-[11px] text-gray-400">
          Deixe em branco para extrair todas as páginas
        </span>
      </div>
      <input
        id="page-range-input"
        type="text"
        value={pageRange}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Ex: 1-5, 8, 12-20 (ou 3- para página 3 até o final)"
        className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      <p className="text-xs text-gray-500">
        Indique as páginas que deseja processar. Aceita intervalos (ex: <code>1-5</code>), páginas
        avulsas (ex: <code>2, 4, 8</code>) ou combinações.
      </p>
    </div>
  );
}

function ListaArquivos({
  files,
  onRemoveFile,
}: {
  files: File[];
  onRemoveFile: (chave: string) => void;
}) {
  if (files.length === 0) return null;
  return (
    <ul className="mt-4 mx-auto max-w-md space-y-1 text-left">
      {files.map((f) => (
        <li
          key={chaveArquivo(f)}
          className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-700"
        >
          <span className="truncate">{f.name}</span>
          <button
            type="button"
            onClick={() => onRemoveFile(chaveArquivo(f))}
            title="Remover arquivo"
            aria-label={`Remover ${f.name}`}
            className="text-gray-400 hover:text-red-600"
          >
            ✕
          </button>
        </li>
      ))}
    </ul>
  );
}

export function CatalogUploadStep({
  files,
  pageRange,
  provider,
  fallbackExternal,
  isDraggingOver,
  onFileChange,
  onRemoveFile,
  onPageRangeChange,
  onProviderChange,
  onFallbackChange,
}: CatalogUploadStepProps) {
  const hasPdf = files.some((f) => f.name.toLowerCase().endsWith(".pdf"));

  return (
    <div className="space-y-6 pt-2">
      <div
        data-testid="catalog-dropzone"
        className={`rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          isDraggingOver
            ? "border-blue-500 bg-blue-50"
            : "border-gray-300 bg-gray-50/50 hover:border-blue-400"
        }`}
      >
        <div className="text-4xl">📄 / 🖼️ / 📝</div>
        <h3 className="mt-2 text-base font-semibold text-gray-900">
          {isDraggingOver
            ? "Solte os arquivos aqui"
            : "Arraste, cole (Ctrl+V) ou selecione o catálogo"}
        </h3>
        <p className="mt-1 text-xs text-gray-500 max-w-md mx-auto">
          Aceita PDF multipáginas, imagens (PNG, JPG, WEBP) e arquivos de texto (TXT, MD, CSV). Você
          também pode colar uma imagem ou um texto copiado.
        </p>
        <div className="mt-4">
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.csv,image/png,image/jpeg,image/webp"
            onChange={onFileChange}
            id="catalog-file-upload"
            className="hidden"
          />
          <label
            htmlFor="catalog-file-upload"
            className="cursor-pointer inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700"
          >
            Procurar Arquivos no Computador
          </label>
        </div>
        <ListaArquivos files={files} onRemoveFile={onRemoveFile} />
      </div>

      {hasPdf && <IntervaloPaginas pageRange={pageRange} onChange={onPageRangeChange} />}

      <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700">
          Modo de Extração de IA
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <OpcaoProvider
            valor="local"
            selecionado={provider === "local"}
            titulo="Híbrido Local (Ollama + pdfplumber)"
            descricao="Rápido, sem custos de API externa para páginas com tabelas e texto legível."
            onChange={onProviderChange}
          />

          <OpcaoProvider
            valor="external"
            selecionado={provider === "external"}
            titulo="Visão Multimodal Externa (OpenRouter)"
            descricao="Lê fotos complexas de encartes, folhetos gráficos e PDFs escaneados."
            onChange={onProviderChange}
          />
        </div>

        <div className="pt-2">
          <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-700">
            <input
              type="checkbox"
              checked={fallbackExternal}
              onChange={(e) => onFallbackChange(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="font-medium">
              Ativar fallback automático para visão multimodal caso a página seja imagem/escaneada
            </span>
          </label>
        </div>
      </div>
    </div>
  );
}
