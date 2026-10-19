"use client";

import React, { useState, useEffect } from "react";
import {
  createAdminProduct,
  updateAdminProduct,
  uploadAdminProductImage,
} from "@/lib/api/adminProducts";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { mensagemDeErro, useProductFormCampos } from "@/lib/hooks/useProductFormCampos";
import { useProductFormExtras } from "@/lib/hooks/useProductFormExtras";
import type { AdminProduct } from "@/lib/types/adminProducts";
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

function ProductFormHeader({
  produtoParaEditar,
  onClose,
}: {
  produtoParaEditar?: AdminProduct | null;
  onClose: () => void;
}) {
  return (
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
  );
}

export default function ProductFormModal({
  isOpen,
  onClose,
  onSuccess,
  produtoParaEditar,
  allProducts = [],
}: ProductFormModalProps) {
  const token = useAuthStore((s) => s.token);
  const [activeTab, setActiveTab] = useState<ActiveTab>("geral");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const campos = useProductFormCampos({ token, produtoParaEditar, onSuccess, setError });
  const extras = useProductFormExtras({ token, produtoParaEditar, onSuccess, setError });
  const { preencher: preencherCampos, novo: novoCampos, fechar: fecharCampos } = campos;
  const { preencher: preencherExtras, limpar: limparExtras } = extras;

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (!isOpen) {
      fecharCampos();
      limparExtras();
      setError(null);
      setActiveTab("geral");
      return;
    }

    if (produtoParaEditar) {
      preencherCampos(produtoParaEditar);
      preencherExtras(produtoParaEditar, token);
    } else {
      novoCampos();
      limparExtras();
    }
    setError(null);
  }, [
    produtoParaEditar,
    isOpen,
    token,
    fecharCampos,
    limparExtras,
    preencherCampos,
    preencherExtras,
    novoCampos,
  ]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!campos.nome.trim()) {
      setError("O nome do produto é obrigatório.");
      return;
    }
    const precoNum = parseFloat(campos.preco);
    if (isNaN(precoNum) || precoNum < 0) {
      setError("Informe um preço de venda válido.");
      return;
    }
    if (!token) return;

    setSaving(true);
    setError(null);
    try {
      const payload: Partial<AdminProduct> = {
        nome: campos.nome.trim(),
        categoria: campos.categoria.trim() || "Geral",
        preco: precoNum,
        preco_base_fornecedor: campos.precoBaseFornecedor
          ? parseFloat(campos.precoBaseFornecedor)
          : null,
        dias_alerta_estoque: campos.diasAlertaEstoque
          ? parseInt(campos.diasAlertaEstoque, 10)
          : null,
        descricao: campos.descricao.trim(),
        especificacoes_tecnicas: campos.especificacoesTecnicas.trim() || null,
      };
      const produtoSalvo = produtoParaEditar
        ? await updateAdminProduct(token, produtoParaEditar.id, payload)
        : await createAdminProduct(token, payload);
      if (campos.imagemFile) await uploadAdminProductImage(token, produtoSalvo.id, campos.imagemFile);
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
        <ProductFormHeader produtoParaEditar={produtoParaEditar} onClose={onClose} />

        {produtoParaEditar && (
          <ProductFormTabs
            activeTab={activeTab}
            estoqueTotal={extras.estoques.reduce((a, b) => a + b.quantidade, 0)}
            descontosCount={extras.descontosVolume.length}
            compatibilidadesCount={extras.compatividades.length}
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
            nome={campos.nome}
            categoria={campos.categoria}
            preco={campos.preco}
            precoBaseFornecedor={campos.precoBaseFornecedor}
            diasAlertaEstoque={campos.diasAlertaEstoque}
            descricao={campos.descricao}
            especificacoesTecnicas={campos.especificacoesTecnicas}
            imagemPreview={campos.imagemPreview}
            imagens={campos.imagens}
            deletingImageId={campos.deletingImageId}
            saving={saving}
            onNome={campos.setNome}
            onCategoria={campos.setCategoria}
            onPreco={campos.setPreco}
            onPrecoBase={campos.setPrecoBaseFornecedor}
            onDiasAlerta={campos.setDiasAlertaEstoque}
            onDescricao={campos.setDescricao}
            onEspecificacoes={campos.setEspecificacoesTecnicas}
            onImageChange={campos.handleImageChange}
            onRemoverImagem={campos.handleRemoverImagemExistente}
            onClose={onClose}
            onSubmit={handleSubmit}
          />
        )}

        {activeTab === "estoque" && produtoParaEditar && (
          <ProductFormEstoqueTab
            estoques={extras.estoques}
            cdNome={extras.cdNome}
            cdQtd={extras.cdQtd}
            updatingStock={extras.updatingStock}
            onCdNome={extras.setCdNome}
            onCdQtd={extras.setCdQtd}
            onSalvar={extras.handleSalvarEstoque}
          />
        )}

        {activeTab === "descontos" && produtoParaEditar && (
          <ProductFormDescontosTab
            descontos={extras.descontosVolume}
            descQtdMin={extras.descQtdMin}
            descPercentual={extras.descPercentual}
            updatingDiscount={extras.updatingDiscount}
            onQtdMin={extras.setDescQtdMin}
            onPercentual={extras.setDescPercentual}
            onAdicionar={extras.handleAdicionarDesconto}
            onRemover={extras.handleRemoverDesconto}
          />
        )}

        {activeTab === "compatibilidades" && produtoParaEditar && (
          <ProductFormCompatibilidadesTab
            produtoId={produtoParaEditar.id}
            compatividades={extras.compatividades}
            compativelSelectedId={extras.compativelSelectedId}
            updatingCompatibility={extras.updatingCompatibility}
            allProducts={allProducts}
            onSelectCompativel={extras.setCompativelSelectedId}
            onAdicionar={extras.handleAdicionarCompatibilidade}
            onRemover={extras.handleRemoverCompatibilidade}
          />
        )}
      </div>
    </div>
  );
}
