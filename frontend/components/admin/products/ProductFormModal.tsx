"use client";

import React, { useState, useEffect } from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import {
  createAdminProduct,
  updateAdminProduct,
  uploadAdminProductImage,
  deleteAdminProductImage,
} from "@/lib/api/adminProducts";
import type { AdminProduct } from "@/lib/types/adminProducts";

interface ProductFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  produtoParaEditar?: AdminProduct | null;
}

export default function ProductFormModal({
  isOpen,
  onClose,
  onSuccess,
  produtoParaEditar,
}: ProductFormModalProps) {
  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState("CFTV");
  const [preco, setPreco] = useState<string>("");
  const [precoBaseFornecedor, setPrecoBaseFornecedor] = useState<string>("");
  const [descricao, setDescricao] = useState("");
  const [especificacoesTecnicas, setEspecificacoesTecnicas] = useState("");
  const [imagemFile, setImagemFile] = useState<File | null>(null);
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (produtoParaEditar) {
      setNome(produtoParaEditar.nome);
      setCategoria(produtoParaEditar.categoria || "Geral");
      setPreco(produtoParaEditar.preco ? String(produtoParaEditar.preco) : "");
      setPrecoBaseFornecedor(
        produtoParaEditar.preco_base_fornecedor
          ? String(produtoParaEditar.preco_base_fornecedor)
          : ""
      );
      setDescricao(produtoParaEditar.descricao || "");
      setEspecificacoesTecnicas(produtoParaEditar.especificacoes_tecnicas || "");
      setImagemPreview(
        produtoParaEditar.imagem_url
          ? produtoParaEditar.imagem_url.startsWith("http")
            ? produtoParaEditar.imagem_url
            : `${getApiBaseUrl()}${produtoParaEditar.imagem_url}`
          : null
      );
      setImagemFile(null);
    } else {
      setNome("");
      setCategoria("CFTV");
      setPreco("");
      setPrecoBaseFornecedor("");
      setDescricao("");
      setEspecificacoesTecnicas("");
      setImagemFile(null);
      setImagemPreview(null);
    }
    setError(null);
  }, [produtoParaEditar, isOpen]);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setImagemFile(file);
      setImagemPreview(URL.createObjectURL(file));
    }
  };

  const handleRemoverImagemExistente = async (imgId: number) => {
    if (!produtoParaEditar) return;
    try {
      await deleteAdminProductImage(produtoParaEditar.id, imgId);
      onSuccess();
    } catch (err: any) {
      setError(err?.message || "Erro ao remover imagem");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!nome.trim()) {
      setError("O nome do produto é obrigatório.");
      return;
    }
    const precoNum = parseFloat(preco);
    if (isNaN(precoNum) || precoNum < 0) {
      setError("Informe um preço de venda válido.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const payload: Partial<AdminProduct> = {
        nome: nome.trim(),
        categoria: categoria.trim() || "Geral",
        preco: precoNum,
        preco_base_fornecedor: precoBaseFornecedor
          ? parseFloat(precoBaseFornecedor)
          : null,
        descricao: descricao.trim(),
        especificacoes_tecnicas: especificacoesTecnicas.trim() || null,
      };

      let produtoSalvo: AdminProduct;
      if (produtoParaEditar) {
        produtoSalvo = await updateAdminProduct(produtoParaEditar.id, payload);
      } else {
        produtoSalvo = await createAdminProduct(payload);
      }

      // Se o usuário selecionou uma nova imagem para upload
      if (imagemFile && produtoSalvo) {
        await uploadAdminProductImage(produtoSalvo.id, imagemFile);
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.message || "Erro ao salvar produto");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-gray-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {produtoParaEditar ? "Editar Produto" : "Novo Produto"}
            </h2>
            <p className="text-xs text-gray-500">
              Preencha os dados comerciais e associe uma foto para busca visual CLIP.
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
          <div className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Nome do Produto *
              </label>
              <input
                type="text"
                required
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                placeholder="Ex: Gravador IP NVD 1016"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Categoria
              </label>
              <input
                type="text"
                list="categorias-list"
                value={categoria}
                onChange={(e) => setCategoria(e.target.value)}
                placeholder="Ex: CFTV"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <datalist id="categorias-list">
                <option value="CFTV" />
                <option value="Alarmes" />
                <option value="Redes" />
                <option value="Controle de Acesso" />
                <option value="Automação" />
                <option value="Geral" />
              </datalist>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Preço Base (Custo)
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={precoBaseFornecedor}
                  onChange={(e) => setPrecoBaseFornecedor(e.target.value)}
                  placeholder="R$ 0,00"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
                  Preço Venda *
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={preco}
                  onChange={(e) => setPreco(e.target.value)}
                  placeholder="R$ 0,00"
                  className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Descrição Comercial
            </label>
            <textarea
              rows={2}
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              placeholder="Descrição do produto para o catálogo e assistente de vendas..."
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
              Especificações Técnicas
            </label>
            <textarea
              rows={2}
              value={especificacoesTecnicas}
              onChange={(e) => setEspecificacoesTecnicas(e.target.value)}
              placeholder="Canais, resolução, alcance IR, voltagem, portas..."
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Imagem e Catálogo Visual CLIP */}
          <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-blue-900">
                  Foto do Produto & Catálogo Visual CLIP
                </h4>
                <p className="text-xs text-blue-700">
                  A imagem é vetorizada automaticamente no Qdrant para reconhecimento por foto no chat.
                </p>
              </div>
              {imagemPreview && (
                <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-gray-200 bg-white">
                  <img
                    src={imagemPreview}
                    alt="Preview"
                    className="h-full w-full object-cover"
                  />
                </div>
              )}
            </div>

            <div className="mt-3">
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={handleImageChange}
                className="block w-full text-xs text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-blue-700"
              />
            </div>

            {/* Imagens já associadas se editando */}
            {produtoParaEditar && produtoParaEditar.imagens && produtoParaEditar.imagens.length > 0 && (
              <div className="mt-3">
                <span className="text-xs font-semibold text-gray-700">
                  Imagens associadas ({produtoParaEditar.imagens.length}):
                </span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {produtoParaEditar.imagens.map((img) => (
                    <div
                      key={img.id}
                      className="group relative h-14 w-14 overflow-hidden rounded border border-gray-200 bg-white"
                    >
                      <img
                        src={
                          img.imagem_url.startsWith("http")
                            ? img.imagem_url
                            : `${getApiBaseUrl()}${img.imagem_url}`
                        }
                        alt="Foto cadastrada"
                        className="h-full w-full object-cover"
                      />
                      <button
                        type="button"
                        onClick={() => handleRemoverImagemExistente(img.id)}
                        title="Remover imagem do produto e do CLIP"
                        className="absolute inset-0 flex items-center justify-center bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        🗑️
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
            >
              {saving ? "Salvando..." : produtoParaEditar ? "Atualizar" : "Salvar Produto"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
