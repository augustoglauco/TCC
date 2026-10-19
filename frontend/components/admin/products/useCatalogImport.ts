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
import {
  arquivoAceito,
  arquivosDoClipboard,
  chaveArquivo,
  nomearArquivoColado,
  payloadConfirmacao,
  produtosDaPagina,
} from "./catalogArquivos";

export type ModalStep = "upload" | "extracting" | "review";

interface UseCatalogImportParams {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

function mensagemErro(err: unknown, padrao: string): string {
  return (err instanceof Error && err.message) || padrao;
}

export function useCatalogImport({ isOpen, onClose, onSuccess }: UseCatalogImportParams) {
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

      const colados = arquivosDoClipboard(data);
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

  const handlePageComplete = (pageRes: CatalogPageResult) => {
    if (pageRes.erro) {
      setPageErrors((prev) => [...prev, `Página ${pageRes.pagina}: ${pageRes.erro}`]);
    }
    const novos = produtosDaPagina(pageRes);
    if (novos.length > 0) setExtractedProducts((prev) => [...prev, ...novos]);
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
        onPageComplete: handlePageComplete,
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

  const pickerHandlers = {
    upload: async (file: File) => {
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
        setError(mensagemErro(err, "Falha ao enviar foto."));
      } finally {
        setUploadingPickerPhoto(false);
      }
    },
    select: (url: string) => {
      if (!pickerProduct) return;
      handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", url);
      setPickerProduct((prev) => (prev ? { ...prev, imagem_temp_url: url } : null));
    },
    remove: () => {
      if (!pickerProduct) return;
      handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", null);
      setPickerProduct((prev) => (prev ? { ...prev, imagem_temp_url: null } : null));
    },
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
      await confirmCatalogExtraction(token, payloadConfirmacao(selected));
      onSuccess();
      onClose();
    } catch (err) {
      setError(mensagemErro(err, "Erro ao gravar lote de produtos"));
    } finally {
      setSaving(false);
    }
  };

  return {
    step,
    setStep,
    files,
    setFiles,
    pageRange,
    setPageRange,
    provider,
    setProvider,
    fallbackExternal,
    setFallbackExternal,
    isDraggingOver,
    progress,
    extractedProducts,
    setExtractedProducts,
    saving,
    error,
    pageErrors,
    pickerProduct,
    setPickerProduct,
    uploadingPickerPhoto,
    selectedCount: extractedProducts.filter((p) => p.selecionado).length,
    handleFileChange,
    handleDragOver,
    handleDragLeave,
    handleDrop,
    handleStartExtraction,
    handleUpdateProduct,
    handleConfirmBatch,
    pickerHandlers,
  };
}
