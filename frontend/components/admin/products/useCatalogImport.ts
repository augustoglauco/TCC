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

function useColarArquivos(ativo: boolean, adicionarArquivos: (novos: File[]) => void) {
  useEffect(() => {
    if (!ativo) return;
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
  }, [ativo, adicionarArquivos]);
}

function useDragDropArquivos(uploadStep: boolean, adicionarArquivos: (novos: File[]) => void) {
  const [isDraggingOver, setIsDraggingOver] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    adicionarArquivos(Array.from(e.target.files ?? []));
    e.target.value = "";
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (uploadStep && !isDraggingOver) setIsDraggingOver(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.currentTarget.contains(e.relatedTarget as Node)) return;
    setIsDraggingOver(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDraggingOver(false);
    if (!uploadStep) return;
    adicionarArquivos(Array.from(e.dataTransfer.files));
  };

  return { isDraggingOver, handleFileChange, handleDragOver, handleDragLeave, handleDrop };
}

type SetError = (msg: string | null) => void;

function useSelecaoArquivos(isOpen: boolean, step: ModalStep, setError: SetError) {
  const [files, setFiles] = useState<File[]>([]);

  const adicionarArquivos = useCallback(
    (novos: File[]) => {
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
    },
    [setError],
  );

  useColarArquivos(isOpen && step === "upload", adicionarArquivos);
  const drag = useDragDropArquivos(step === "upload", adicionarArquivos);

  return { files, setFiles, ...drag };
}

type AtualizarProduto = (
  idTemp: string | undefined,
  field: keyof ExtractedProductItem,
  value: ExtractedProductItem[keyof ExtractedProductItem],
) => void;

function usePickerFoto(
  token: string | null,
  handleUpdateProduct: AtualizarProduto,
  setError: SetError,
) {
  const [pickerProduct, setPickerProduct] = useState<ExtractedProductItem | null>(null);
  const [uploadingPickerPhoto, setUploadingPickerPhoto] = useState(false);

  const atualizarPicker = (patch: Partial<ExtractedProductItem>) =>
    setPickerProduct((prev) => (prev ? { ...prev, ...patch } : null));

  const definirFoto = (url: string | null) => {
    if (!pickerProduct) return;
    handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", url);
    atualizarPicker({ imagem_temp_url: url });
  };

  const enviarFoto = async (file: File) => {
    if (!pickerProduct || !token) return;
    setUploadingPickerPhoto(true);
    try {
      const url = await uploadTempImage(token, file);
      const fotos = [...(pickerProduct.fotos_pagina ?? []), url];
      handleUpdateProduct(pickerProduct.id_temporario, "imagem_temp_url", url);
      handleUpdateProduct(pickerProduct.id_temporario, "fotos_pagina", fotos);
      atualizarPicker({ imagem_temp_url: url, fotos_pagina: fotos });
    } catch (err) {
      setError(mensagemErro(err, "Falha ao enviar foto."));
    } finally {
      setUploadingPickerPhoto(false);
    }
  };

  const pickerHandlers = {
    upload: enviarFoto,
    select: (url: string) => definirFoto(url),
    remove: () => definirFoto(null),
  };

  return { pickerProduct, setPickerProduct, uploadingPickerPhoto, pickerHandlers };
}

function useOpcoesExtracao() {
  const [pageRange, setPageRange] = useState("");
  const [provider, setProvider] = useState<"local" | "external">("local");
  const [fallbackExternal, setFallbackExternal] = useState(true);
  return { pageRange, setPageRange, provider, setProvider, fallbackExternal, setFallbackExternal };
}

interface ExtracaoDeps {
  token: string | null;
  files: File[];
  opcoes: ReturnType<typeof useOpcoesExtracao>;
  setStep: (s: ModalStep) => void;
  setError: SetError;
}

function useExtracaoCatalogo({ token, files, opcoes, setStep, setError }: ExtracaoDeps) {
  const [progress, setProgress] = useState<CatalogExtractionProgress>({
    pagina: 0,
    total: 0,
    status: "",
  });
  const [extractedProducts, setExtractedProducts] = useState<ExtractedProductItem[]>([]);
  const [pageErrors, setPageErrors] = useState<string[]>([]);

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

    const { provider, fallbackExternal, pageRange } = opcoes;
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

  const handleUpdateProduct: AtualizarProduto = (idTemp, field, value) => {
    setExtractedProducts((prev) =>
      prev.map((item) => (item.id_temporario === idTemp ? { ...item, [field]: value } : item)),
    );
  };

  return {
    progress,
    extractedProducts,
    setExtractedProducts,
    pageErrors,
    handleStartExtraction,
    handleUpdateProduct,
  };
}

function useConfirmarLote(
  token: string | null,
  extractedProducts: ExtractedProductItem[],
  setError: SetError,
  onConcluido: () => void,
) {
  const [saving, setSaving] = useState(false);

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
      onConcluido();
    } catch (err) {
      setError(mensagemErro(err, "Erro ao gravar lote de produtos"));
    } finally {
      setSaving(false);
    }
  };

  return { saving, handleConfirmBatch };
}

export function useCatalogImport({ isOpen, onClose, onSuccess }: UseCatalogImportParams) {
  const token = useAuthStore((s) => s.token);
  const [step, setStep] = useState<ModalStep>("upload");
  const [error, setError] = useState<string | null>(null);

  const selecao = useSelecaoArquivos(isOpen, step, setError);
  const opcoes = useOpcoesExtracao();
  const extracao = useExtracaoCatalogo({ token, files: selecao.files, opcoes, setStep, setError });
  const picker = usePickerFoto(token, extracao.handleUpdateProduct, setError);
  const { saving, handleConfirmBatch } = useConfirmarLote(
    token,
    extracao.extractedProducts,
    setError,
    () => {
      onSuccess();
      onClose();
    },
  );

  return {
    step,
    setStep,
    ...selecao,
    ...opcoes,
    ...extracao,
    saving,
    error,
    pickerProduct: picker.pickerProduct,
    setPickerProduct: picker.setPickerProduct,
    uploadingPickerPhoto: picker.uploadingPickerPhoto,
    pickerHandlers: picker.pickerHandlers,
    selectedCount: extracao.extractedProducts.filter((p) => p.selecionado).length,
    handleConfirmBatch,
  };
}
