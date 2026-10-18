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
import { ProductFormGeralTab } from "./ProductFormGeralTab";
import { ProductFormEstoqueTab } from "./ProductFormEstoqueTab";
import { ProductFormDescontosTab } from "./ProductFormDescontosTab";
import { ProductFormCompatibilidadesTab } from "./ProductFormCompatibilidadesTab";
import { ProductFormTabs, type ActiveTab } from "./ProductFormTabs";

interface ProductFormModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (produtoAtualizado?: AdminProduct) => void;
  produtoParaEditar?: AdminProduct | null;
  allProducts?: AdminProduct[];
}

function resolveImageUrl(url?: string | null): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${getApiBaseUrl()}${url}`;
}

function mensagemDeErro(err: unknown, fallback: string): string {
  return (err instanceof Error && err.message) || fallback;
}

const descontoValido = (qtdMin: number, perc: number) =>
  !isNaN(qtdMin) && qtdMin > 0 && !isNaN(perc) && perc > 0;

export default function ProductFormModal({
  isOpen,
  onClose,
  onSuccess,
  produtoParaEditar,
  allProducts = [],
}: ProductFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const [activeTab, setActiveTab] = useState<ActiveTab>("geral");

  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState("CFTV");
  const [preco, setPreco] = useState("");
  const [precoBaseFornecedor, setPrecoBaseFornecedor] = useState("");
  const [diasAlertaEstoque, setDiasAlertaEstoque] = useState("");
  const [descricao, setDescricao] = useState("");
  const [especificacoesTecnicas, setEspecificacoesTecnicas] = useState("");
  const [imagemFile, setImagemFile] = useState<File | null>(null);
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);
  const [imagens, setImagens] = useState<AdminProductImage[]>([]);
  const [deletingImageId, setDeletingImageId] = useState<number | null>(null);

  const [estoques, setEstoques] = useState<AdminProductStock[]>([]);
  const [cdNome, setCdNome] = useState("CD-Matriz");
  const [cdQtd, setCdQtd] = useState("10");
  const [updatingStock, setUpdatingStock] = useState(false);

  const [descontosVolume, setDescontosVolume] = useState<AdminProductVolumeDiscount[]>([]);
  const [descQtdMin, setDescQtdMin] = useState("5");
  const [descPercentual, setDescPercentual] = useState("10");
  const [updatingDiscount, setUpdatingDiscount] = useState(false);

  const [compatividades, setCompatividades] = useState<AdminProductCompatibility[]>([]);
  const [compativelSelectedId, setCompativelSelectedId] = useState("");
  const [updatingCompatibility, setUpdatingCompatibility] = useState(false);

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) {
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
      setDiasAlertaEstoque(
        produtoParaEditar.dias_alerta_estoque ? String(produtoParaEditar.dias_alerta_estoque) : "",
      );
      setDescricao(produtoParaEditar.descricao || "");
      setEspecificacoesTecnicas(produtoParaEditar.especificacoes_tecnicas || "");
      setImagemPreview(resolveImageUrl(produtoParaEditar.imagem_url));
      setImagens(produtoParaEditar.imagens || []);
      setEstoques(produtoParaEditar.estoques || []);
      setDescontosVolume(produtoParaEditar.descontos_volume || []);
      setImagemFile(null);
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
      setDiasAlertaEstoque("");
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
  }, [produtoParaEditar, isOpen, token]);

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
        if (!imagemFile) setImagemPreview(resolveImageUrl(produtoAtualizado.imagem_url));
      } catch {
        const previewRemovido =
          !imagemFile && imagemRemovida && imagemPreview?.includes(imagemRemovida.imagem_url);
        if (previewRemovido) setImagemPreview(resolveImageUrl(imagensRestantes[0]?.imagem_url));
      }
      onSuccess(produtoAtualizado || undefined);
    } catch (err) {
      if (imagemRemovida) setImagens((prev) => [...prev, imagemRemovida]);
      setError(mensagemDeErro(err, "Erro ao remover imagem"));
    } finally {
      setDeletingImageId(null);
    }
  };

  const executarAcao = async (
    setBusy: (busy: boolean) => void,
    mensagemFalha: string,
    acao: () => Promise<void>,
  ) => {
    setBusy(true);
    setError(null);
    try {
      await acao();
    } catch (err) {
      setError(mensagemDeErro(err, mensagemFalha));
    } finally {
      setBusy(false);
    }
  };

  const handleSalvarEstoque = async () => {
    if (!produtoParaEditar || !cdNome.trim() || !token) return;
    const qtd = parseInt(cdQtd, 10);
    if (isNaN(qtd) || qtd < 0) {
      setError("Informe uma quantidade válida de estoque.");
      return;
    }
    await executarAcao(setUpdatingStock, "Erro ao atualizar estoque", async () => {
      const prod = await updateAdminProductStock(token, produtoParaEditar.id, cdNome.trim(), qtd);
      setEstoques(prod.estoques || []);
      onSuccess(prod);
    });
  };

  const handleAdicionarDesconto = async () => {
    if (!produtoParaEditar || !token) return;
    const qtdMin = parseInt(descQtdMin, 10);
    const perc = parseFloat(descPercentual);
    if (!descontoValido(qtdMin, perc)) {
      setError("Informe quantidade mínima (>0) e percentual válido (>0).");
      return;
    }
    await executarAcao(setUpdatingDiscount, "Erro ao adicionar faixa de desconto", async () => {
      const prod = await addAdminProductVolumeDiscount(token, produtoParaEditar.id, qtdMin, perc);
      setDescontosVolume(prod.descontos_volume || []);
      onSuccess(prod);
    });
  };

  const handleRemoverDesconto = async (descontoId: string) => {
    if (!produtoParaEditar || !token) return;
    await executarAcao(setUpdatingDiscount, "Erro ao excluir faixa de desconto", async () => {
      const prod = await deleteAdminProductVolumeDiscount(token, produtoParaEditar.id, descontoId);
      setDescontosVolume(prod.descontos_volume || []);
      onSuccess(prod);
    });
  };

  const handleAdicionarCompatibilidade = async () => {
    if (!produtoParaEditar || !compativelSelectedId || !token) return;
    const targetId = parseInt(compativelSelectedId, 10);
    if (isNaN(targetId) || targetId === produtoParaEditar.id) return;
    await executarAcao(setUpdatingCompatibility, "Erro ao adicionar compatibilidade", async () => {
      setCompatividades(await addAdminProductCompatibility(token, produtoParaEditar.id, targetId));
      setCompativelSelectedId("");
    });
  };

  const handleRemoverCompatibilidade = async (compativelComId: number) => {
    if (!produtoParaEditar || !token) return;
    await executarAcao(setUpdatingCompatibility, "Erro ao remover compatibilidade", async () => {
      setCompatividades(
        await deleteAdminProductCompatibility(token, produtoParaEditar.id, compativelComId),
      );
    });
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
        dias_alerta_estoque: diasAlertaEstoque ? parseInt(diasAlertaEstoque, 10) : null,
        descricao: descricao.trim(),
        especificacoes_tecnicas: especificacoesTecnicas.trim() || null,
      };
      const produtoSalvo = produtoParaEditar
        ? await updateAdminProduct(token, produtoParaEditar.id, payload)
        : await createAdminProduct(token, payload);
      if (imagemFile) await uploadAdminProductImage(token, produtoSalvo.id, imagemFile);
      onSuccess();
      onClose();
    } catch (err) {
      setError(mensagemDeErro(err, "Erro ao salvar produto"));
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl space-y-4">
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

        {produtoParaEditar && (
          <ProductFormTabs
            activeTab={activeTab}
            estoqueTotal={estoques.reduce((a, b) => a + b.quantidade, 0)}
            descontosCount={descontosVolume.length}
            compatibilidadesCount={compatividades.length}
            onChange={setActiveTab}
          />
        )}

        {error && (
          <div className="rounded-lg bg-red-50 p-3 text-xs font-semibold text-red-700 border border-red-200">
            {error}
          </div>
        )}

        {(activeTab === "geral" || !produtoParaEditar) && (
          <ProductFormGeralTab
            produtoParaEditar={produtoParaEditar}
            nome={nome}
            categoria={categoria}
            preco={preco}
            precoBaseFornecedor={precoBaseFornecedor}
            diasAlertaEstoque={diasAlertaEstoque}
            descricao={descricao}
            especificacoesTecnicas={especificacoesTecnicas}
            imagemPreview={imagemPreview}
            imagens={imagens}
            deletingImageId={deletingImageId}
            saving={saving}
            onNome={setNome}
            onCategoria={setCategoria}
            onPreco={setPreco}
            onPrecoBase={setPrecoBaseFornecedor}
            onDiasAlerta={setDiasAlertaEstoque}
            onDescricao={setDescricao}
            onEspecificacoes={setEspecificacoesTecnicas}
            onImageChange={handleImageChange}
            onRemoverImagem={handleRemoverImagemExistente}
            onClose={onClose}
            onSubmit={handleSubmit}
          />
        )}

        {activeTab === "estoque" && produtoParaEditar && (
          <ProductFormEstoqueTab
            estoques={estoques}
            cdNome={cdNome}
            cdQtd={cdQtd}
            updatingStock={updatingStock}
            onCdNome={setCdNome}
            onCdQtd={setCdQtd}
            onSalvar={handleSalvarEstoque}
          />
        )}

        {activeTab === "descontos" && produtoParaEditar && (
          <ProductFormDescontosTab
            descontos={descontosVolume}
            descQtdMin={descQtdMin}
            descPercentual={descPercentual}
            updatingDiscount={updatingDiscount}
            onQtdMin={setDescQtdMin}
            onPercentual={setDescPercentual}
            onAdicionar={handleAdicionarDesconto}
            onRemover={handleRemoverDesconto}
          />
        )}

        {activeTab === "compatibilidades" && produtoParaEditar && (
          <ProductFormCompatibilidadesTab
            produtoId={produtoParaEditar.id}
            compatividades={compatividades}
            compativelSelectedId={compativelSelectedId}
            updatingCompatibility={updatingCompatibility}
            allProducts={allProducts}
            onSelectCompativel={setCompativelSelectedId}
            onAdicionar={handleAdicionarCompatibilidade}
            onRemover={handleRemoverCompatibilidade}
          />
        )}
      </div>
    </div>
  );
}
