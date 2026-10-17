"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  extractCatalogStream,
  confirmCatalogExtraction,
  uploadTempImage,
} from "@/lib/api/adminProducts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type {
  ExtractedProductItem,
  CatalogExtractionProgress,
  CatalogPageResult,
} from "@/lib/types/adminProducts";
import { CatalogUploadStep } from "./CatalogUploadStep";
import { CatalogExtractingStep } from "./CatalogExtractingStep";
import { CatalogReviewStep } from "./CatalogReviewStep";
import { CatalogPhotoPicker } from "./CatalogPhotoPicker";

interface CatalogImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

type ModalStep = "upload" | "extracting" | "review";

const EXTENSOES_ACEITAS = /\.(pdf|png|jpe?g|webp|txt|md|csv)$/i;
const TIPOS_IMAGEM_ACEITOS = ["image/png", "image/jpeg", "image/webp"];
const TIPOS_TEXTO_ACEITOS = ["text/plain", "text/markdown", "text/csv"];

function arquivoAceito(file: File): boolean {
  return (
    file.type === "application/pdf" ||
    TIPOS_IMAGEM_ACEITOS.includes(file.type) ||
    TIPOS_TEXTO_ACEITOS.includes(file.type) ||
    EXTENSOES_ACEITAS.test(file.name)
  );
}

function chaveArquivo(file: File): string {
  return `${file.name}|${file.size}|${file.lastModified}`;
}

function nomearArquivoColado(file: File, indice: number): File {
  if (!/^image\.\w+$/i.test(file.name)) return file;
  const extensao = file.name.split(".").pop();
  return new File([file], `imagem-colada-${Date.now()}-${indice}.${extensao}`, {
    type: file.type,
    lastModified: file.lastModified,
  });
}

// ─── Utilitários de moeda (exportados para uso em testes e CatalogReviewStep) ─

interface CatalogPriceInputProps {
  value: number | null | undefined;
  onChange: (val: number | null) => void;
  isBold?: boolean;
  ariaLabel?: string;
}

export function formatarMoedaInput(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || isNaN(valor)) return "";
  return valor.toLocaleString("pt-BR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function parseMoedaInput(texto: string): number | null {
  const limpo = texto.trim().replace(/[^\d,.-]/g, "");
  if (!limpo) return null;
  let normalizado = limpo;
  if (normalizado.includes(",") && normalizado.includes(".")) {
    normalizado = normalizado.replace(/\./g, "").replace(",", ".");
  } else if (normalizado.includes(",")) {
    normalizado = normalizado.replace(",", ".");
  }
  const num = parseFloat(normalizado);
  return isNaN(num) ? null : Number(num.toFixed(2));
}

export function CatalogPriceInput({
  value,
  onChange,
  isBold = false,
  ariaLabel,
}: CatalogPriceInputProps) {
  const [texto, setTexto] = useState(() => formatarMoedaInput(value));
  const [focado, setFocado] = useState(false);

  const [valueAnterior, setValueAnterior] = useState(value);
  if (value !== valueAnterior && !focado) {
    setValueAnterior(value);
    setTexto(formatarMoedaInput(value));
  }

  const handleBlur = () => {
    setFocado(false);
    const parsed = parseMoedaInput(texto);
    onChange(parsed);
    setTexto(formatarMoedaInput(parsed));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const novoTexto = e.target.value;
    setTexto(novoTexto);
    onChange(parseMoedaInput(novoTexto));
  };

  return (
    <div className="relative flex items-center rounded border border-gray-300 bg-white transition-colors focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 shadow-2xs">
      <span className="pl-2 pr-0.5 text-[11px] font-semibold text-gray-500 select-none">R$</span>
      <input
        type="text"
        inputMode="decimal"
        value={texto}
        onChange={handleChange}
        onFocus={(e) => {
          setFocado(true);
          e.target.select();
        }}
        onBlur={handleBlur}
        placeholder="0,00"
        aria-label={ariaLabel}
        className={`w-full bg-transparent px-1.5 py-1 text-right text-xs focus:outline-none ${
          isBold ? "font-bold text-gray-900" : "font-medium text-gray-700"
        }`}
      />
    </div>
  );
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function CatalogImportModal({
  isOpen,
  onClose,
  onSuccess,
}: CatalogImportModalProps) {
  const token = useAuthStore((s) => s.token);
  const [step, setStep] = useState<ModalStep>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [pageRange, setPageRange] = useState("");
  const [provider, setProvider] = useState<"local" | "external">("local");
  const [fallbackExternal, setFallbackExternal] = useState(true);
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [progress, setProgress] = useState<CatalogExtractionProgress>({
    pagina: 0,
    total: 0,
    status: "",
  });
  const [extractedProducts, setExtractedProducts] = useState<ExtractedProductItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageErrors, setPageErrors] = useState<string[]>([]);
  const [pickerProduct, setPickerProduct] = useState<ExtractedProductItem | null>(null);
  const [uploadingPickerPhoto, setUploadingPickerPhoto] = useState(false);

  const adicionarArquivos = useCallback((novos: File[]) => {
    if (novos.length === 0) return;
    const aceitos = novos.filter(arquivoAceito);
    const rejeitados = novos.filter((f) => !arquivoAceito(f));
    setError(
      rejeitados.length > 0
        ? `Tipo não suportado: ${rejeitados.map((f) => f.name).join(", ")}. Use PDF, imagem (PNG, JPG, WEBP) ou texto (TXT, MD, CSV).`
        : null,
    );
    if (aceitos.length === 0) return;
    setFiles((prev) => {
      const existentes = new Set(prev.map(chaveArquivo));
      return [...prev, ...aceitos.filter((f) => !existentes.has(chaveArquivo(f)))];
    });
  }, []);

  const uploadAtivo = isOpen && step === "upload";

  useEffect(() => {
    if (!uploadAtivo) return;
    const onPaste = (e: ClipboardEvent) => {
      const alvo = e.target as HTMLElement | null;
      if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA")) return;
      const data = e.clipboardData;
      if (!data) return;

      let colados = Array.from(data.files);
      if (colados.length === 0) {
        colados = Array.from(data.items)
          .filter((item) => item.kind === "file")
          .map((item) => item.getAsFile())
          .filter((f): f is File => f !== null);
      }
      if (colados.length > 0) {
        e.preventDefault();
        adicionarArquivos(colados.map(nomearArquivoColado));
        return;
      }

      const texto = data.getData("text/plain");
      if (texto.trim()) {
        e.preventDefault();
        adicionarArquivos([
          new File([texto], `texto-colado-${Date.now()}.txt`, { type: "text/plain" }),
        ]);
      }
    };
    document.addEventListener("paste", onPaste);
    return () => document.removeEventListener("paste", onPaste);
  }, [uploadAtivo, adicionarArquivos]);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    adicionarArquivos(Array.from(e.target.files ?? []));
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (step === "upload" && !isDraggingOver) setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingOver(false);
    if (step !== "upload") return;
    adicionarArquivos(Array.from(e.dataTransfer.files));
  };

  const handleStartExtraction = async () => {
    if (files.length === 0) {
      setError("Selecione pelo menos um arquivo de catálogo (PDF, imagens ou texto).");
      return;
    }
    if (!token) return;

    setStep("extracting");
    setError(null);
    setExtractedProducts([]);
    setPageErrors([]);
    setProgress({ pagina: 0, total: 0, status: "Iniciando processamento..." });

    await extractCatalogStream(
      token,
      files,
      { provider, fallbackExternal, pageRange: pageRange.trim() || undefined },
      {
        onProgress: (p) => setProgress(p),
        onPageComplete: (pageRes: CatalogPageResult) => {
          if (pageRes.erro) {
            setPageErrors((prev) => [...prev, `Página ${pageRes.pagina}: ${pageRes.erro}`]);
          }
          if (pageRes.produtos && pageRes.produtos.length > 0) {
            setExtractedProducts((prev) => [
              ...prev,
              ...pageRes.produtos.map((p, idx) => ({
                ...p,
                id_temporario: `${pageRes.pagina}_${idx}_${Date.now()}`,
                selecionado: true,
                preco:
                  p.preco ||
                  (p.preco_base_fornecedor
                    ? Number((p.preco_base_fornecedor * 1.35).toFixed(2))
                    : null),
              })),
            ]);
          }
        },
        onDone: () => setStep("review"),
        onError: (err) => {
          setError(err);
          setStep("upload");
        },
      },
    );
  };

  const handleUpdateProduct = (
    idTemp: string | undefined,
    field: keyof ExtractedProductItem,
    value: ExtractedProductItem[keyof ExtractedProductItem],
  ) => {
    setExtractedProducts((prev) =>
      prev.map((item) => (item.id_temporario === idTemp ? { ...item, [field]: value } : item)),
    );
  };

  const handleUploadPhotoForProduct = async (file: File) => {
    if (!pickerProduct || !token) return;
    setUploadingPickerPhoto(true);
    try {
      const url = await uploadTempImage(token, file);
      const updatedFotos = pickerProduct.fotos_pagina
        ? [...pickerProduct.fotos_pagina, url]
        : [url];
      handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", url);
      handleUpdateProduct(pickerProduct.id_temporario, "fotos_pagina", updatedFotos);
      setPickerProduct((prev) =>
        prev ? { ...prev, imagem_temp_url: url, fotos_pagina: updatedFotos } : null,
      );
    } catch (err) {
      setError((err instanceof Error && err.message) || "Falha ao enviar foto.");
    } finally {
      setUploadingPickerPhoto(false);
    }
  };

  const handleSelectPagePhoto = (url: string) => {
    if (!pickerProduct) return;
    handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", url);
    setPickerProduct((prev) => (prev ? { ...prev, imagem_temp_url: url } : null));
  };

  const handleRemovePhoto = () => {
    if (!pickerProduct) return;
    handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", null);
    setPickerProduct((prev) => (prev ? { ...prev, imagem_temp_url: null } : null));
  };

  const handleConfirmBatch = async () => {
    const selected = extractedProducts.filter((p) => p.selecionado);
    if (selected.length === 0) {
      setError("Selecione pelo menos um produto para salvar no catálogo.");
      return;
    }
    if (!token) return;

    setSaving(true);
    setError(null);
    try {
      await confirmCatalogExtraction(token, {
        produtos: selected.map((p) => ({
          nome: p.nome,
          descricao: p.descricao || "",
          categoria: p.categoria || "Geral",
          preco_base_fornecedor: p.preco_base_fornecedor,
          preco: p.preco || p.preco_base_fornecedor || 0,
          especificacoes_tecnicas: p.especificacoes_tecnicas || null,
          imagem_temp_url: p.imagem_temp_url || null,
        })),
      });
      onSuccess();
      onClose();
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao gravar lote de produtos");
    } finally {
      setSaving(false);
    }
  };

  const selectedCount = extractedProducts.filter((p) => p.selecionado).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div
        className="relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="flex items-center justify-between border-b border-gray-100 p-6 pb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <span>📥</span> Importação Inteligente de Catálogos
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Leitura página a página de PDF multipáginas, imagens ou arquivos de texto com extração
              via IA e revisão antes de salvar.
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

        {error && (
          <div className="mx-6 mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        <div className="flex-1 overflow-y-auto p-6 pt-2">
          {step === "upload" && (
            <CatalogUploadStep
              files={files}
              pageRange={pageRange}
              provider={provider}
              fallbackExternal={fallbackExternal}
              isDraggingOver={isDraggingOver}
              onFileChange={handleFileChange}
              onRemoveFile={(chave) =>
                setFiles((prev) => prev.filter((f) => chaveArquivo(f) !== chave))
              }
              onPageRangeChange={setPageRange}
              onProviderChange={setProvider}
              onFallbackChange={setFallbackExternal}
            />
          )}

          {step === "extracting" && (
            <CatalogExtractingStep progress={progress} extractedCount={extractedProducts.length} />
          )}

          {step === "review" && (
            <CatalogReviewStep
              products={extractedProducts}
              pageErrors={pageErrors}
              onToggleSelectAll={(checked) =>
                setExtractedProducts((prev) =>
                  prev.map((item) => ({ ...item, selecionado: checked })),
                )
              }
              onUpdateProduct={handleUpdateProduct}
              onRemoveProduct={(idTemp) =>
                setExtractedProducts((prev) => prev.filter((item) => item.id_temporario !== idTemp))
              }
              onOpenPhotoPicker={setPickerProduct}
            />
          )}
        </div>

        <div className="flex items-center justify-between border-t border-gray-100 bg-gray-50 px-6 py-4">
          <div>
            {step === "review" && (
              <span className="text-xs font-semibold text-gray-700">
                {selectedCount} de {extractedProducts.length} produto(s) selecionados para gravação
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {step === "upload" && (
              <>
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleStartExtraction}
                  disabled={files.length === 0}
                  className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
                >
                  Iniciar Extração Inteligente
                </button>
              </>
            )}

            {step === "review" && (
              <>
                <button
                  type="button"
                  onClick={() => setStep("upload")}
                  disabled={saving}
                  className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200"
                >
                  ← Voltar
                </button>
                <button
                  type="button"
                  onClick={handleConfirmBatch}
                  disabled={saving || selectedCount === 0}
                  className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
                >
                  {saving
                    ? "Gravando e Vetorizando no CLIP..."
                    : `Confirmar e Gravar ${selectedCount} Produto(s)`}
                </button>
              </>
            )}
          </div>
        </div>

        {pickerProduct && (
          <CatalogPhotoPicker
            product={pickerProduct}
            uploading={uploadingPickerPhoto}
            onSelectPhoto={handleSelectPagePhoto}
            onRemovePhoto={handleRemovePhoto}
            onUploadPhoto={handleUploadPhotoForProduct}
            onClose={() => setPickerProduct(null)}
          />
        )}
      </div>
    </div>
  );
}
