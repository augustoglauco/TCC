"use client";

import React, { useCallback, useEffect, useState } from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
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

// Imagens coladas chegam todas com o nome "image.png"; nomes únicos evitam
// que uma sobrescreva/duplique a outra na lista e no log do backend.
function nomearArquivoColado(file: File, indice: number): File {
  if (!/^image\.\w+$/i.test(file.name)) return file;
  const extensao = file.name.split(".").pop();
  return new File([file], `imagem-colada-${Date.now()}-${indice}.${extensao}`, {
    type: file.type,
    lastModified: file.lastModified,
  });
}

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

  useEffect(() => {
    if (!focado) {
      setTexto(formatarMoedaInput(value));
    }
  }, [value, focado]);

  const handleBlur = () => {
    setFocado(false);
    const parsed = parseMoedaInput(texto);
    onChange(parsed);
    setTexto(formatarMoedaInput(parsed));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const novoTexto = e.target.value;
    setTexto(novoTexto);
    const parsed = parseMoedaInput(novoTexto);
    onChange(parsed);
  };

  return (
    <div className="relative flex items-center rounded border border-gray-300 bg-white transition-colors focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 shadow-2xs">
      <span className="pl-2 pr-0.5 text-[11px] font-semibold text-gray-500 select-none">
        R$
      </span>
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

  // Progresso SSE
  const [progress, setProgress] = useState<CatalogExtractionProgress>({
    pagina: 0,
    total: 0,
    status: "",
  });

  // Produtos extraídos acumulados para revisão
  const [extractedProducts, setExtractedProducts] = useState<ExtractedProductItem[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Erros de extração por página/imagem (ex.: vision externo indisponível) —
  // distintos de "nenhum produto encontrado" (página processada com sucesso,
  // mas sem produto nela).
  const [pageErrors, setPageErrors] = useState<string[]>([]);

  // Seletor / troca de foto do produto
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

  // Colar (Ctrl+V): arquivos/imagens da área de transferência e, se nada
  // estiver focado num campo de texto, texto puro vira um arquivo .txt.
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
    // Sempre cancela o comportamento padrão, senão soltar fora da área
    // faria o navegador abrir o arquivo na própria aba.
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

  const handleRemoveFile = (chave: string) => {
    setFiles((prev) => prev.filter((f) => chaveArquivo(f) !== chave));
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
                // Sugestão de markup padrão de 35% no preço de venda se não veio definido
                preco:
                  p.preco ||
                  (p.preco_base_fornecedor
                    ? Number((p.preco_base_fornecedor * 1.35).toFixed(2))
                    : null),
              })),
            ]);
          }
        },
        onDone: () => {
          setStep("review");
        },
        onError: (err) => {
          setError(err);
          setStep("upload");
        },
      },
    );
  };

  const handleToggleSelectAll = (checked: boolean) => {
    setExtractedProducts((prev) => prev.map((item) => ({ ...item, selecionado: checked })));
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

  const handleRemoveProduct = (idTemp: string | undefined) => {
    setExtractedProducts((prev) => prev.filter((item) => item.id_temporario !== idTemp));
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
        prev
          ? {
              ...prev,
              imagem_temp_url: url,
              fotos_pagina: updatedFotos,
            }
          : null,
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
  const hasPdf = files.some((f) => f.name.toLowerCase().endsWith(".pdf"));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div
        className="relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Header */}
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

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6 pt-2">
          {/* STEP 1: UPLOAD */}
          {step === "upload" && (
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
                  Aceita PDF multipáginas, imagens (PNG, JPG, WEBP) e arquivos de texto (TXT, MD,
                  CSV). Você também pode colar uma imagem ou um texto copiado.
                </p>
                <div className="mt-4">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,.txt,.md,.csv,image/png,image/jpeg,image/webp"
                    onChange={handleFileChange}
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
                {files.length > 0 && (
                  <ul className="mt-4 mx-auto max-w-md space-y-1 text-left">
                    {files.map((f) => (
                      <li
                        key={chaveArquivo(f)}
                        className="flex items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-700"
                      >
                        <span className="truncate">{f.name}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveFile(chaveArquivo(f))}
                          title="Remover arquivo"
                          aria-label={`Remover ${f.name}`}
                          className="text-gray-400 hover:text-red-600"
                        >
                          ✕
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Intervalo de Páginas do PDF */}
              {hasPdf && (
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
                    onChange={(e) => setPageRange(e.target.value)}
                    placeholder="Ex: 1-5, 8, 12-20 (ou 3- para página 3 até o final)"
                    className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <p className="text-xs text-gray-500">
                    Indique as páginas que deseja processar. Aceita intervalos (ex: <code>1-5</code>
                    ), páginas avulsas (ex: <code>2, 4, 8</code>) ou combinações.
                  </p>
                </div>
              )}

              {/* Opções de IA e Processamento */}
              <div className="rounded-xl border border-gray-200 bg-white p-4 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Modo de Extração de IA
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <label
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-all ${
                      provider === "local"
                        ? "border-blue-600 bg-blue-50/40 ring-1 ring-blue-600"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="provider"
                      value="local"
                      checked={provider === "local"}
                      onChange={() => setProvider("local")}
                      className="mt-1 text-blue-600"
                    />
                    <div>
                      <span className="block text-sm font-semibold text-gray-900">
                        Híbrido Local (Ollama + pdfplumber)
                      </span>
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Rápido, sem custos de API externa para páginas com tabelas e texto legível.
                      </span>
                    </div>
                  </label>

                  <label
                    className={`flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-all ${
                      provider === "external"
                        ? "border-blue-600 bg-blue-50/40 ring-1 ring-blue-600"
                        : "border-gray-200 hover:bg-gray-50"
                    }`}
                  >
                    <input
                      type="radio"
                      name="provider"
                      value="external"
                      checked={provider === "external"}
                      onChange={() => setProvider("external")}
                      className="mt-1 text-blue-600"
                    />
                    <div>
                      <span className="block text-sm font-semibold text-gray-900">
                        Visão Multimodal Externa (OpenRouter)
                      </span>
                      <span className="block text-xs text-gray-500 mt-0.5">
                        Lê fotos complexas de encartes, folhetos gráficos e PDFs escaneados.
                      </span>
                    </div>
                  </label>
                </div>

                <div className="pt-2">
                  <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-700">
                    <input
                      type="checkbox"
                      checked={fallbackExternal}
                      onChange={(e) => setFallbackExternal(e.target.checked)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="font-medium">
                      Ativar fallback automático para visão multimodal caso a página seja
                      imagem/escaneada
                    </span>
                  </label>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: EXTRACTING (LIVE SSE) */}
          {step === "extracting" && (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-4">
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-blue-600 border-t-transparent" />
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  Lendo catálogo e identificando produtos...
                </h3>
                <p className="text-sm text-gray-500 mt-1 max-w-md">
                  {progress.status || "Processando páginas..."}
                </p>
              </div>

              {progress.total > 0 && (
                <div className="w-full max-w-md mt-4">
                  <div className="flex justify-between text-xs font-semibold text-gray-600 mb-1">
                    <span>
                      Página {progress.pagina} de {progress.total}
                    </span>
                    <span>{Math.round((progress.pagina / progress.total) * 100)}%</span>
                  </div>
                  <div className="h-2 w-full rounded-full bg-gray-200 overflow-hidden">
                    <div
                      className="h-full bg-blue-600 transition-all duration-300 rounded-full"
                      style={{
                        width: `${Math.min(100, Math.round((progress.pagina / progress.total) * 100))}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              <div className="text-xs text-blue-600 font-medium">
                {extractedProducts.length} produto(s) identificado(s) até o momento...
              </div>
            </div>
          )}

          {/* STEP 3: REVIEW (HUMAN-IN-THE-LOOP TABLE) */}
          {step === "review" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between bg-blue-50 p-3 rounded-lg border border-blue-100">
                <div className="text-xs text-blue-900">
                  <strong>Conferência Prévia:</strong> Revise os dados extraídos, ajuste nomes e
                  preços ou desmarque produtos que não deseja incluir.
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleToggleSelectAll(true)}
                    className="text-xs text-blue-700 font-semibold underline hover:text-blue-900"
                  >
                    Marcar Todos
                  </button>
                  <span className="text-gray-300">|</span>
                  <button
                    type="button"
                    onClick={() => handleToggleSelectAll(false)}
                    className="text-xs text-blue-700 font-semibold underline hover:text-blue-900"
                  >
                    Desmarcar Todos
                  </button>
                </div>
              </div>

              {pageErrors.length > 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800">
                  <p className="font-semibold mb-1">
                    {extractedProducts.length === 0
                      ? "Não foi possível extrair produtos — houve falha ao processar:"
                      : "Algumas páginas falharam durante a extração:"}
                  </p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {pageErrors.map((msg, idx) => (
                      <li key={idx}>{msg}</li>
                    ))}
                  </ul>
                </div>
              )}

              {extractedProducts.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">
                  {pageErrors.length === 0
                    ? "Nenhum produto foi detectado nos arquivos fornecidos."
                    : "Nenhum produto foi extraído — corrija o problema acima e tente novamente."}
                </div>
              ) : (
                <div className="overflow-x-auto rounded-xl border border-gray-200">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-gray-50 text-gray-500 font-semibold uppercase tracking-wider border-b border-gray-200">
                        <th className="p-3 w-8">Sel.</th>
                        <th className="p-3 w-16">Foto</th>
                        <th className="p-3">Nome do Produto</th>
                        <th className="p-3 w-32">Categoria</th>
                        <th className="p-3 w-32">Preço Revend.</th>
                        <th className="p-3 w-32">Preço Venda</th>
                        <th className="p-3">Descrição / Specs</th>
                        <th className="p-3 w-10 text-right"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      {extractedProducts.map((item) => (
                        <tr
                          key={item.id_temporario}
                          className={
                            item.selecionado ? "hover:bg-blue-50/20" : "opacity-50 bg-gray-50"
                          }
                        >
                          <td className="p-3">
                            <input
                              type="checkbox"
                              checked={Boolean(item.selecionado)}
                              onChange={(e) =>
                                handleUpdateProduct(
                                  item.id_temporario,
                                  "selecionado",
                                  e.target.checked,
                                )
                              }
                              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-3">
                            <div className="flex flex-col items-center gap-1">
                              <button
                                type="button"
                                onClick={() => setPickerProduct(item)}
                                title="Clique para trocar a foto ou escolher outra da página"
                                className="group relative h-12 w-12 rounded-lg border border-gray-200 bg-gray-50 overflow-hidden flex items-center justify-center hover:border-blue-500 hover:ring-2 hover:ring-blue-200 transition-all cursor-pointer"
                              >
                                {item.imagem_temp_url ? (
                                  <img
                                    src={
                                      item.imagem_temp_url.startsWith("http")
                                        ? item.imagem_temp_url
                                        : `${getApiBaseUrl()}${item.imagem_temp_url}`
                                    }
                                    alt="Preview"
                                    className="h-full w-full object-contain p-0.5"
                                  />
                                ) : (
                                  <span className="text-gray-400 group-hover:scale-110 transition-transform">
                                    📷
                                  </span>
                                )}
                                <div className="absolute inset-0 bg-black/45 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-[10px] font-bold transition-opacity">
                                  Trocar
                                </div>
                              </button>
                              {item.fotos_pagina && item.fotos_pagina.length > 1 && (
                                <button
                                  type="button"
                                  onClick={() => setPickerProduct(item)}
                                  className="text-[10px] text-blue-600 hover:text-blue-800 font-medium underline"
                                >
                                  {item.fotos_pagina.length} fotos
                                </button>
                              )}
                            </div>
                          </td>
                          <td className="p-3">
                            <input
                              type="text"
                              value={item.nome}
                              onChange={(e) =>
                                handleUpdateProduct(item.id_temporario, "nome", e.target.value)
                              }
                              className="w-full rounded border border-gray-300 px-2 py-1 font-medium text-gray-900 focus:border-blue-500 focus:outline-none"
                            />
                          </td>
                          <td className="p-3">
                            <input
                              type="text"
                              value={item.categoria || ""}
                              onChange={(e) =>
                                handleUpdateProduct(item.id_temporario, "categoria", e.target.value)
                              }
                              className="w-full rounded border border-gray-300 px-2 py-1 text-gray-700 focus:border-blue-500 focus:outline-none"
                            />
                          </td>
                          <td className="p-3">
                            <CatalogPriceInput
                              value={item.preco_base_fornecedor}
                              onChange={(val) =>
                                handleUpdateProduct(
                                  item.id_temporario,
                                  "preco_base_fornecedor",
                                  val,
                                )
                              }
                              ariaLabel={`Preço revenda ${item.nome}`}
                            />
                          </td>
                          <td className="p-3">
                            <CatalogPriceInput
                              value={item.preco}
                              onChange={(val) =>
                                handleUpdateProduct(
                                  item.id_temporario,
                                  "preco",
                                  val,
                                )
                              }
                              isBold
                              ariaLabel={`Preço venda ${item.nome}`}
                            />
                          </td>
                          <td className="p-3">
                            <input
                              type="text"
                              value={item.descricao || item.especificacoes_tecnicas || ""}
                              onChange={(e) =>
                                handleUpdateProduct(item.id_temporario, "descricao", e.target.value)
                              }
                              className="w-full rounded border border-gray-300 px-2 py-1 text-gray-600 focus:border-blue-500 focus:outline-none"
                            />
                          </td>
                          <td className="p-3 text-right">
                            <button
                              type="button"
                              onClick={() => handleRemoveProduct(item.id_temporario)}
                              title="Descartar item"
                              className="text-gray-400 hover:text-red-600"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
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

        {/* Modal de Seleção / Troca de Foto do Produto */}
        {pickerProduct && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-xs">
            <div className="relative w-full max-w-lg rounded-xl bg-white p-5 shadow-2xl space-y-4">
              <div className="flex items-center justify-between border-b pb-3 border-gray-100">
                <div>
                  <h3 className="text-sm font-bold text-gray-900 flex items-center gap-1.5">
                    <span>🖼️</span> Selecionar Foto do Produto
                  </h3>
                  <p className="text-xs text-gray-500 truncate max-w-sm mt-0.5">
                    {pickerProduct.nome}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setPickerProduct(null)}
                  className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                >
                  ✕
                </button>
              </div>

              {/* Foto atual */}
              <div className="flex items-center gap-4 bg-gray-50 p-3 rounded-lg border border-gray-200">
                <div className="h-16 w-16 rounded border bg-white overflow-hidden flex items-center justify-center shrink-0">
                  {pickerProduct.imagem_temp_url ? (
                    <img
                      src={
                        pickerProduct.imagem_temp_url.startsWith("http")
                          ? pickerProduct.imagem_temp_url
                          : `${getApiBaseUrl()}${pickerProduct.imagem_temp_url}`
                      }
                      alt="Foto selecionada"
                      className="h-full w-full object-contain p-1"
                    />
                  ) : (
                    <span className="text-xs text-gray-400 text-center">Sem foto</span>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-gray-700">Foto Atual</div>
                  <div className="text-[11px] text-gray-500">
                    {pickerProduct.imagem_temp_url
                      ? "Figura recortada associada ao produto"
                      : "Nenhuma foto selecionada"}
                  </div>
                </div>
                {pickerProduct.imagem_temp_url && (
                  <button
                    type="button"
                    onClick={handleRemovePhoto}
                    className="text-xs text-red-600 hover:text-red-800 font-semibold px-2 py-1 rounded hover:bg-red-50"
                  >
                    Remover Foto
                  </button>
                )}
              </div>

              {/* Galeria de fotos detectadas na página */}
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1.5">
                  Fotos Detectadas no Catálogo (Página {pickerProduct.pagina_origem || 1})
                </label>
                {pickerProduct.fotos_pagina && pickerProduct.fotos_pagina.length > 0 ? (
                  <div className="grid grid-cols-4 sm:grid-cols-5 gap-2 max-h-48 overflow-y-auto p-1 bg-gray-50/50 rounded-lg border border-gray-200">
                    {pickerProduct.fotos_pagina.map((fotoUrl, fIdx) => {
                      const isSelected = pickerProduct.imagem_temp_url === fotoUrl;
                      return (
                        <button
                          key={fIdx}
                          type="button"
                          onClick={() => handleSelectPagePhoto(fotoUrl)}
                          className={`relative aspect-square rounded-lg border-2 bg-white overflow-hidden p-1 flex items-center justify-center hover:opacity-90 transition-all ${
                            isSelected
                              ? "border-blue-600 ring-2 ring-blue-400"
                              : "border-gray-200 hover:border-gray-400"
                          }`}
                        >
                          <img
                            src={
                              fotoUrl.startsWith("http") ? fotoUrl : `${getApiBaseUrl()}${fotoUrl}`
                            }
                            alt={`Figura ${fIdx + 1}`}
                            className="h-full w-full object-contain"
                          />
                          {isSelected && (
                            <span className="absolute top-1 right-1 flex h-4 w-4 items-center justify-center rounded-full bg-blue-600 text-[10px] text-white font-bold">
                              ✓
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div className="text-xs text-gray-500 italic p-3 bg-gray-50 rounded-lg text-center">
                    Nenhuma figura individual foi identificada nesta página.
                  </div>
                )}
              </div>

              {/* Upload de foto alternativa do computador */}
              <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
                <div>
                  <input
                    type="file"
                    accept="image/*"
                    id="picker-upload-file"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        handleUploadPhotoForProduct(e.target.files[0]);
                      }
                    }}
                  />
                  <label
                    htmlFor="picker-upload-file"
                    className="cursor-pointer inline-flex items-center gap-1.5 text-xs font-semibold text-blue-600 hover:text-blue-800 bg-blue-50 px-3 py-1.5 rounded-lg border border-blue-200 hover:bg-blue-100"
                  >
                    <span>📁</span>{" "}
                    {uploadingPickerPhoto ? "Enviando..." : "Enviar Foto do Computador"}
                  </label>
                </div>
                <button
                  type="button"
                  onClick={() => setPickerProduct(null)}
                  className="rounded-lg bg-gray-900 px-4 py-1.5 text-xs font-semibold text-white hover:bg-gray-800"
                >
                  Concluir
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
