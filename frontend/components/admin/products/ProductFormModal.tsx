"use client";

import React, { useState, useEffect } from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import {
  createAdminProduct,
  updateAdminProduct,
  uploadAdminProductImage,
  deleteAdminProductImage,
  fetchAdminProduct,
  updateAdminProductStock,
  addAdminProductVolumeDiscount,
  deleteAdminProductVolumeDiscount,
  fetchAdminProductCompatibilities,
  addAdminProductCompatibility,
  deleteAdminProductCompatibility,
} from "@/lib/api/adminProducts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import type {
  AdminProduct,
  AdminProductImage,
  AdminProductStock,
  AdminProductVolumeDiscount,
  AdminProductCompatibility,
} from "@/lib/types/adminProducts";
import SearchableSelect from "@/components/ui/SearchableSelect";

interface ProductFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (produtoAtualizado?: AdminProduct) => void;
  produtoParaEditar?: AdminProduct | null;
  allProducts?: AdminProduct[];
}

export default function ProductFormModal({
  isOpen,
  onClose,
  onSuccess,
  produtoParaEditar,
  allProducts = [],
}: ProductFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const [activeTab, setActiveTab] = useState<
    "geral" | "estoque" | "descontos" | "compatibilidades"
  >("geral");

  // Dados Básicos
  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState("CFTV");
  const [preco, setPreco] = useState<string>("");
  const [precoBaseFornecedor, setPrecoBaseFornecedor] = useState<string>("");
  const [descricao, setDescricao] = useState("");
  const [especificacoesTecnicas, setEspecificacoesTecnicas] = useState("");
  const [imagemFile, setImagemFile] = useState<File | null>(null);
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);
  const [imagens, setImagens] = useState<AdminProductImage[]>([]);
  const [deletingImageId, setDeletingImageId] = useState<number | null>(null);

  // Estoque
  const [estoques, setEstoques] = useState<AdminProductStock[]>([]);
  const [cdNome, setCdNome] = useState("CD-Matriz");
  const [cdQtd, setCdQtd] = useState<string>("10");
  const [updatingStock, setUpdatingStock] = useState(false);

  // Descontos por Volume
  const [descontosVolume, setDescontosVolume] = useState<AdminProductVolumeDiscount[]>([]);
  const [descQtdMin, setDescQtdMin] = useState<string>("5");
  const [descPercentual, setDescPercentual] = useState<string>("10");
  const [updatingDiscount, setUpdatingDiscount] = useState(false);

  // Compatibilidades
  const [compatividades, setCompatividades] = useState<AdminProductCompatibility[]>([]);
  const [compativelSelectedId, setCompativelSelectedId] = useState<string>("");
  const [updatingCompatibility, setUpdatingCompatibility] = useState(false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
      // Zera o formulário ao fechar o modal (sincronização com a prop `isOpen`)
      // — padrão aceito no projeto para `react-hooks/set-state-in-effect`.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setImagemFile(null);
      setImagemPreview(null);
      setImagens([]);
      setEstoques([]);
      setDescontosVolume([]);
      setCompatividades([]);
      setError(null);
      setActiveTab("geral");
      return;
    }

    if (produtoParaEditar) {
      setNome(produtoParaEditar.nome);
      setCategoria(produtoParaEditar.categoria || "Geral");
      setPreco(produtoParaEditar.preco ? String(produtoParaEditar.preco) : "");
      setPrecoBaseFornecedor(
        produtoParaEditar.preco_base_fornecedor
          ? String(produtoParaEditar.preco_base_fornecedor)
          : "",
      );
      setDescricao(produtoParaEditar.descricao || "");
      setEspecificacoesTecnicas(produtoParaEditar.especificacoes_tecnicas || "");
      setImagemPreview(
        produtoParaEditar.imagem_url
          ? produtoParaEditar.imagem_url.startsWith("http")
            ? produtoParaEditar.imagem_url
            : `${getApiBaseUrl()}${produtoParaEditar.imagem_url}`
          : null,
      );
      setImagens(produtoParaEditar.imagens || []);
      setEstoques(produtoParaEditar.estoques || []);
      setDescontosVolume(produtoParaEditar.descontos_volume || []);
      setImagemFile(null);

      // Carrega compatibilidades remotas
      if (token) {
        fetchAdminProductCompatibilities(token, produtoParaEditar.id)
          .then(setCompatividades)
          .catch(() => setCompatividades([]));
      }
    } else {
      setNome("");
      setCategoria("CFTV");
      setPreco("");
      setPrecoBaseFornecedor("");
      setDescricao("");
      setEspecificacoesTecnicas("");
      setImagemFile(null);
      setImagemPreview(null);
      setImagens([]);
      setEstoques([]);
      setDescontosVolume([]);
      setCompatividades([]);
    }
    setError(null);
  }, [produtoParaEditar?.id, isOpen, token]);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setImagemFile(file);
      setImagemPreview(URL.createObjectURL(file));
    }
  };

  const handleRemoverImagemExistente = async (imgId: number) => {
    if (!produtoParaEditar || deletingImageId !== null || !token) return;
    setDeletingImageId(imgId);
    setError(null);

    const imagemRemovida = imagens.find((img) => img.id === imgId);
    const imagensRestantes = imagens.filter((img) => img.id !== imgId);
    setImagens(imagensRestantes);

    try {
      await deleteAdminProductImage(token, produtoParaEditar.id, imgId);
      let produtoAtualizado: AdminProduct | null = null;
      try {
        produtoAtualizado = await fetchAdminProduct(token, produtoParaEditar.id);
        setImagens(produtoAtualizado.imagens || []);
        if (!imagemFile) {
          setImagemPreview(
            produtoAtualizado.imagem_url
              ? produtoAtualizado.imagem_url.startsWith("http")
                ? produtoAtualizado.imagem_url
                : `${getApiBaseUrl()}${produtoAtualizado.imagem_url}`
              : null,
          );
        }
      } catch {
        if (!imagemFile && imagemRemovida && imagemPreview?.includes(imagemRemovida.imagem_url)) {
          const proximaImg = imagensRestantes[0];
          setImagemPreview(
            proximaImg
              ? proximaImg.imagem_url.startsWith("http")
                ? proximaImg.imagem_url
                : `${getApiBaseUrl()}${proximaImg.imagem_url}`
              : null,
          );
        }
      }
      onSuccess(produtoAtualizado || undefined);
    } catch (err) {
      if (imagemRemovida) setImagens((prev) => [...prev, imagemRemovida]);
      setError((err instanceof Error && err.message) || "Erro ao remover imagem");
    } finally {
      setDeletingImageId(null);
    }
  };

  // Handlers de Estoque
  const handleSalvarEstoque = async () => {
    if (!produtoParaEditar || !cdNome.trim() || !token) return;
    const qtd = parseInt(cdQtd, 10);
    if (isNaN(qtd) || qtd < 0) {
      setError("Informe uma quantidade válida de estoque.");
      return;
    }
    setUpdatingStock(true);
    setError(null);
    try {
      const prodAtualizado = await updateAdminProductStock(
        token,
        produtoParaEditar.id,
        cdNome.trim(),
        qtd,
      );
      setEstoques(prodAtualizado.estoques || []);
      onSuccess(prodAtualizado);
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao atualizar estoque");
    } finally {
      setUpdatingStock(false);
    }
  };

  // Handlers de Desconto por Volume
  const handleAdicionarDesconto = async () => {
    if (!produtoParaEditar || !token) return;
    const qtdMin = parseInt(descQtdMin, 10);
    const perc = parseFloat(descPercentual);
    if (isNaN(qtdMin) || qtdMin <= 0 || isNaN(perc) || perc <= 0) {
      setError("Informe quantidade mínima (>0) e percentual válido (>0).");
      return;
    }
    setUpdatingDiscount(true);
    setError(null);
    try {
      const prodAtualizado = await addAdminProductVolumeDiscount(
        token,
        produtoParaEditar.id,
        qtdMin,
        perc,
      );
      setDescontosVolume(prodAtualizado.descontos_volume || []);
      onSuccess(prodAtualizado);
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao adicionar faixa de desconto");
    } finally {
      setUpdatingDiscount(false);
    }
  };

  const handleRemoverDesconto = async (descontoId: string) => {
    if (!produtoParaEditar || !token) return;
    setUpdatingDiscount(true);
    setError(null);
    try {
      const prodAtualizado = await deleteAdminProductVolumeDiscount(
        token,
        produtoParaEditar.id,
        descontoId,
      );
      setDescontosVolume(prodAtualizado.descontos_volume || []);
      onSuccess(prodAtualizado);
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao excluir faixa de desconto");
    } finally {
      setUpdatingDiscount(false);
    }
  };

  // Handlers de Compatibilidade
  const handleAdicionarCompatibilidade = async () => {
    if (!produtoParaEditar || !compativelSelectedId || !token) return;
    const targetId = parseInt(compativelSelectedId, 10);
    if (isNaN(targetId) || targetId === produtoParaEditar.id) return;
    setUpdatingCompatibility(true);
    setError(null);
    try {
      const list = await addAdminProductCompatibility(token, produtoParaEditar.id, targetId);
      setCompatividades(list);
      setCompativelSelectedId("");
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao adicionar compatibilidade");
    } finally {
      setUpdatingCompatibility(false);
    }
  };

  const handleRemoverCompatibilidade = async (compativelComId: number) => {
    if (!produtoParaEditar || !token) return;
    setUpdatingCompatibility(true);
    setError(null);
    try {
      const list = await deleteAdminProductCompatibility(
        token,
        produtoParaEditar.id,
        compativelComId,
      );
      setCompatividades(list);
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao remover compatibilidade");
    } finally {
      setUpdatingCompatibility(false);
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
    if (!token) return;

    setSaving(true);
    setError(null);

    try {
      const payload: Partial<AdminProduct> = {
        nome: nome.trim(),
        categoria: categoria.trim() || "Geral",
        preco: precoNum,
        preco_base_fornecedor: precoBaseFornecedor ? parseFloat(precoBaseFornecedor) : null,
        descricao: descricao.trim(),
        especificacoes_tecnicas: especificacoesTecnicas.trim() || null,
      };

      let produtoSalvo: AdminProduct;
      if (produtoParaEditar) {
        produtoSalvo = await updateAdminProduct(token, produtoParaEditar.id, payload);
      } else {
        produtoSalvo = await createAdminProduct(token, payload);
      }

      if (imagemFile && produtoSalvo) {
        await uploadAdminProductImage(token, produtoSalvo.id, imagemFile);
      }

      onSuccess();
      onClose();
    } catch (err) {
      setError((err instanceof Error && err.message) || "Erro ao salvar produto");
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl space-y-4">
        {/* Cabeçalho */}
        <div className="flex items-center justify-between border-b border-gray-100 pb-4">
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              {produtoParaEditar ? produtoParaEditar.nome : "Novo Produto"}
            </h2>
            <p className="text-xs text-gray-500">
              Cadastre dados comerciais, estoque por CD, faixas de desconto por volume e
              compatibilidades.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-600 cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Abas de Navegação interna (quando editando) */}
        {produtoParaEditar && (
          <div className="flex border-b border-slate-200 gap-2">
            <button
              type="button"
              onClick={() => setActiveTab("geral")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all cursor-pointer border-b-2 ${
                activeTab === "geral"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              📝 Informações Gerais & Fotos
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("estoque")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all cursor-pointer border-b-2 ${
                activeTab === "estoque"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              📦 Estoque por CD ({estoques.reduce((a, b) => a + b.quantidade, 0)})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("descontos")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all cursor-pointer border-b-2 ${
                activeTab === "descontos"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              🏷️ Descontos Volume ({descontosVolume.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("compatibilidades")}
              className={`pb-2.5 px-3 text-xs font-bold transition-all cursor-pointer border-b-2 ${
                activeTab === "compatibilidades"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              🔗 Compatibilidade ({compatividades.length})
            </button>
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-xs font-semibold text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {/* ABA 1: Geral & Fotos */}
        {(activeTab === "geral" || !produtoParaEditar) && (
          <form onSubmit={handleSubmit} className="space-y-4">
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
                    Preço Revendedor
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
                    A imagem é vetorizada automaticamente no Qdrant para reconhecimento por foto no
                    chat.
                  </p>
                </div>
                {imagemPreview && (
                  <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-gray-200 bg-white">
                    <img src={imagemPreview} alt="Preview" className="h-full w-full object-cover" />
                  </div>
                )}
              </div>

              <div className="mt-3">
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={handleImageChange}
                  className="block w-full text-xs text-gray-500 file:mr-4 file:rounded-md file:border-0 file:bg-blue-600 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-white hover:file:bg-blue-700 cursor-pointer"
                />
              </div>

              {produtoParaEditar && imagens.length > 0 && (
                <div className="mt-3">
                  <span className="text-xs font-semibold text-gray-700">
                    Imagens associadas ({imagens.length}):
                  </span>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {imagens.map((img) => {
                      const isDeleting = deletingImageId === img.id;
                      return (
                        <div
                          key={img.id}
                          className={`group relative h-14 w-14 overflow-hidden rounded border border-gray-200 bg-white ${
                            isDeleting ? "opacity-40" : ""
                          }`}
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
                            disabled={deletingImageId !== null}
                            onClick={() => handleRemoverImagemExistente(img.id)}
                            title="Remover imagem do produto e do CLIP"
                            className="absolute inset-0 flex items-center justify-center bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity disabled:cursor-not-allowed cursor-pointer"
                          >
                            {isDeleting ? "⏳" : "🗑️"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
              <button
                type="button"
                onClick={onClose}
                disabled={saving}
                className="rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 cursor-pointer"
              >
                Cancelar
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
              >
                {saving ? "Salvando..." : produtoParaEditar ? "Atualizar Dados" : "Salvar Produto"}
              </button>
            </div>
          </form>
        )}

        {/* ABA 2: Estoque por Centro de Distribuição */}
        {activeTab === "estoque" && produtoParaEditar && (
          <div className="space-y-4 py-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                📦 Atualizar Estoque por Centro de Distribuição
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700">
                    Centro de Distribuição
                  </label>
                  <select
                    value={cdNome}
                    onChange={(e) => setCdNome(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 focus:border-blue-500 focus:outline-none"
                  >
                    <option value="CD-Matriz">CD-Matriz</option>
                    <option value="CD-SP">CD-SP</option>
                    <option value="CD-RJ">CD-RJ</option>
                    <option value="CD-Sul">CD-Sul</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700">
                    Quantidade em Estoque
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={cdQtd}
                    onChange={(e) => setCdQtd(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    type="button"
                    disabled={updatingStock}
                    onClick={handleSalvarEstoque}
                    className="w-full rounded-lg bg-blue-600 py-2 px-4 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs"
                  >
                    {updatingStock ? "Salvando..." : "Atualizar Estoque"}
                  </button>
                </div>
              </div>
            </div>

            {/* Lista de Estoques do Produto */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Estoques Cadastrados
              </h4>
              {estoques.length === 0 ? (
                <p className="text-xs text-slate-400 italic">
                  Nenhum registro de estoque em CD ainda.
                </p>
              ) : (
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                  {estoques.map((est) => (
                    <div key={est.id} className="flex items-center justify-between p-3 text-xs">
                      <span className="font-semibold text-slate-900">
                        {est.centro_distribuicao}
                      </span>
                      <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded border border-emerald-200">
                        {est.quantidade} unidades
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ABA 3: Descontos em Volume */}
        {activeTab === "descontos" && produtoParaEditar && (
          <div className="space-y-4 py-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                🏷️ Adicionar Faixa de Desconto por Volume
              </h3>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-700">
                    Qtd Mínima (Unidades)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={descQtdMin}
                    onChange={(e) => setDescQtdMin(e.target.value)}
                    placeholder="ex: 5"
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700">Desconto (%)</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="100"
                    value={descPercentual}
                    onChange={(e) => setDescPercentual(e.target.value)}
                    placeholder="ex: 10"
                    className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-mono text-slate-900 focus:border-blue-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-end">
                  <button
                    type="button"
                    disabled={updatingDiscount}
                    onClick={handleAdicionarDesconto}
                    className="w-full rounded-lg bg-blue-600 py-2 px-4 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs"
                  >
                    {updatingDiscount ? "Adicionando..." : "+ Adicionar Faixa"}
                  </button>
                </div>
              </div>
            </div>

            {/* Lista de Faixas de Desconto */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Faixas de Desconto Ativas
              </h4>
              {descontosVolume.length === 0 ? (
                <p className="text-xs text-slate-400 italic">
                  Nenhum desconto por volume configurado.
                </p>
              ) : (
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                  {descontosVolume.map((desc) => (
                    <div key={desc.id} className="flex items-center justify-between p-3 text-xs">
                      <div>
                        <span className="font-semibold text-slate-900">
                          A partir de {desc.quantidade_minima} unidades:
                        </span>
                        <span className="ml-2 font-mono font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
                          {desc.percentual_desconto}% OFF
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoverDesconto(desc.id)}
                        className="text-red-500 hover:text-red-700 font-bold p-1 cursor-pointer"
                        title="Remover faixa de desconto"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ABA 4: Compatibilidade de Produtos */}
        {activeTab === "compatibilidades" && produtoParaEditar && (
          <div className="space-y-4 py-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
                🔗 Vincular Produto Compatível
              </h3>

              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Selecione o produto compatível do catálogo
                  </label>
                  <SearchableSelect
                    options={allProducts
                      .filter((p) => p.id !== produtoParaEditar.id)
                      .map((p) => ({
                        value: String(p.id),
                        label: `#${p.id} - ${p.nome}`,
                        sublabel: p.categoria || "Sem categoria",
                      }))}
                    value={compativelSelectedId}
                    onChange={(val) => setCompativelSelectedId(val)}
                    placeholder="-- Pesquise e selecione um produto --"
                    disabled={updatingCompatibility}
                  />
                </div>

                <div className="flex items-end">
                  <button
                    type="button"
                    disabled={!compativelSelectedId || updatingCompatibility}
                    onClick={handleAdicionarCompatibilidade}
                    className="w-full sm:w-auto rounded-lg bg-blue-600 py-2 px-5 text-xs font-bold text-white hover:bg-blue-700 disabled:opacity-50 transition-all cursor-pointer shadow-2xs shrink-0"
                  >
                    {updatingCompatibility ? "Viculando..." : "+ Vincular Compatível"}
                  </button>
                </div>
              </div>
            </div>

            {/* Lista de Compatibilidades */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Produtos Compatíveis Conectados
              </h4>
              {compatividades.length === 0 ? (
                <p className="text-xs text-slate-400 italic">
                  Nenhum vínculo de compatibilidade cadastrado ainda.
                </p>
              ) : (
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
                  {compatividades.map((comp) => (
                    <div key={comp.id} className="flex items-center justify-between p-3 text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-slate-400">#{comp.compativel_com_id}</span>
                        <span className="font-semibold text-slate-900">{comp.compativel_nome}</span>
                        {comp.categoria && (
                          <span className="text-[10px] font-semibold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                            {comp.categoria}
                          </span>
                        )}
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemoverCompatibilidade(comp.compativel_com_id)}
                        className="text-red-500 hover:text-red-700 font-bold p-1 cursor-pointer"
                        title="Desvincular compatibilidade"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
