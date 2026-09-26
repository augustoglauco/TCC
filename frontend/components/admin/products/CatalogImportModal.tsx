"use client";

import React, { useState } from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import { extractCatalogStream, confirmCatalogExtraction } from "@/lib/api/adminProducts";
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

export default function CatalogImportModal({
  isOpen,
  onClose,
  onSuccess,
}: CatalogImportModalProps) {
  const [step, setStep] = useState<ModalStep>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [provider, setProvider] = useState<"local" | "external">("local");
  const [fallbackExternal, setFallbackExternal] = useState(true);

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

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleStartExtraction = async () => {
    if (files.length === 0) {
      setError("Selecione pelo menos um arquivo de catálogo (PDF ou imagens).");
      return;
    }

    setStep("extracting");
    setError(null);
    setExtractedProducts([]);
    setProgress({ pagina: 0, total: 0, status: "Iniciando processamento..." });

    await extractCatalogStream(
      files,
      { provider, fallbackExternal },
      {
        onProgress: (p) => setProgress(p),
        onPageComplete: (pageRes: CatalogPageResult) => {
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
      }
    );
  };

  const handleToggleSelectAll = (checked: boolean) => {
    setExtractedProducts((prev) =>
      prev.map((item) => ({ ...item, selecionado: checked }))
    );
  };

  const handleUpdateProduct = (idTemp: string | undefined, field: keyof ExtractedProductItem, value: any) => {
    setExtractedProducts((prev) =>
      prev.map((item) =>
        item.id_temporario === idTemp ? { ...item, [field]: value } : item
      )
    );
  };

  const handleRemoveProduct = (idTemp: string | undefined) => {
    setExtractedProducts((prev) =>
      prev.filter((item) => item.id_temporario !== idTemp)
    );
  };

  const handleConfirmBatch = async () => {
    const selected = extractedProducts.filter((p) => p.selecionado);
    if (selected.length === 0) {
      setError("Selecione pelo menos um produto para salvar no catálogo.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await confirmCatalogExtraction({
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
    } catch (err: any) {
      setError(err?.message || "Erro ao gravar lote de produtos");
    } finally {
      setSaving(false);
    }
  };

  const selectedCount = extractedProducts.filter((p) => p.selecionado).length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl bg-white shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-100 p-6 pb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <span>📥</span> Importação Inteligente de Catálogos
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Leitura página a página de PDF multipáginas ou pastas de imagens com extração via IA e revisão antes de salvar.
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
          <div className="mx-6 mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Content area */}
        <div className="flex-1 overflow-y-auto p-6 pt-2">
          {/* STEP 1: UPLOAD */}
          {step === "upload" && (
            <div className="space-y-6 pt-2">
              <div className="rounded-xl border-2 border-dashed border-gray-300 p-8 text-center hover:border-blue-400 transition-colors bg-gray-50/50">
                <div className="text-4xl">📄 / 🖼️</div>
                <h3 className="mt-2 text-base font-semibold text-gray-900">
                  Selecione o catálogo ou as imagens
                </h3>
                <p className="mt-1 text-xs text-gray-500 max-w-md mx-auto">
                  Envie arquivo PDF multipáginas com tabelas de produtos ou selecione múltiplos folders/fotos de folhetos promocionais.
                </p>
                <div className="mt-4">
                  <input
                    type="file"
                    multiple
                    accept=".pdf,image/png,image/jpeg,image/webp"
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
                  <div className="mt-3 text-xs font-semibold text-blue-700">
                    {files.length} arquivo(s) selecionado(s) ({files.map((f) => f.name).join(", ")})
                  </div>
                )}
              </div>

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
                      Ativar fallback automático para visão multimodal caso a página seja imagem/escaneada
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
                    <span>Página {progress.pagina} de {progress.total}</span>
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
                  <strong>Conferência Prévia:</strong> Revise os dados extraídos, ajuste nomes e preços ou desmarque produtos que não deseja incluir.
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

              {extractedProducts.length === 0 ? (
                <div className="text-center py-8 text-gray-500 text-sm">
                  Nenhum produto foi detectado nos arquivos fornecidos.
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
                        <th className="p-3 w-28">Preço Fornec.</th>
                        <th className="p-3 w-28">Preço Venda</th>
                        <th className="p-3">Descrição / Specs</th>
                        <th className="p-3 w-10 text-right"></th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200 bg-white">
                      {extractedProducts.map((item) => (
                        <tr
                          key={item.id_temporario}
                          className={item.selecionado ? "hover:bg-blue-50/20" : "opacity-50 bg-gray-50"}
                        >
                          <td className="p-3">
                            <input
                              type="checkbox"
                              checked={Boolean(item.selecionado)}
                              onChange={(e) =>
                                handleUpdateProduct(item.id_temporario, "selecionado", e.target.checked)
                              }
                              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            />
                          </td>
                          <td className="p-3">
                            <div className="h-12 w-12 rounded border border-gray-200 bg-gray-100 overflow-hidden flex items-center justify-center">
                              {item.imagem_temp_url ? (
                                <img
                                  src={
                                    item.imagem_temp_url.startsWith("http")
                                      ? item.imagem_temp_url
                                      : `${getApiBaseUrl()}${item.imagem_temp_url}`
                                  }
                                  alt="Preview"
                                  className="h-full w-full object-cover"
                                />
                              ) : (
                                <span className="text-gray-400">📷</span>
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
                            <input
                              type="number"
                              step="0.01"
                              value={item.preco_base_fornecedor ?? ""}
                              onChange={(e) =>
                                handleUpdateProduct(
                                  item.id_temporario,
                                  "preco_base_fornecedor",
                                  e.target.value ? parseFloat(e.target.value) : null
                                )
                              }
                              className="w-full rounded border border-gray-300 px-2 py-1 text-gray-700 focus:border-blue-500 focus:outline-none"
                            />
                          </td>
                          <td className="p-3">
                            <input
                              type="number"
                              step="0.01"
                              value={item.preco ?? ""}
                              onChange={(e) =>
                                handleUpdateProduct(
                                  item.id_temporario,
                                  "preco",
                                  e.target.value ? parseFloat(e.target.value) : null
                                )
                              }
                              className="w-full rounded border border-gray-300 px-2 py-1 font-bold text-gray-900 focus:border-blue-500 focus:outline-none"
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
      </div>
    </div>
  );
}
