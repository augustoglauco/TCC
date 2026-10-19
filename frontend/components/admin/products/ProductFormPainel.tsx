"use client";

import React from "react";
import type { useProductFormCampos } from "@/lib/hooks/useProductFormCampos";
import type { useProductFormExtras } from "@/lib/hooks/useProductFormExtras";
import type { AdminProduct } from "@/lib/types/adminProducts";
import { ProductFormGeralTab } from "./ProductFormGeralTab";
import { ProductFormEstoqueTab } from "./ProductFormEstoqueTab";
import { ProductFormDescontosTab } from "./ProductFormDescontosTab";
import { ProductFormCompatibilidadesTab } from "./ProductFormCompatibilidadesTab";
import type { ActiveTab } from "./ProductFormTabs";

interface ProductFormPainelProps {
  activeTab: ActiveTab;
  produtoParaEditar?: AdminProduct | null;
  allProducts: AdminProduct[];
  campos: ReturnType<typeof useProductFormCampos>;
  extras: ReturnType<typeof useProductFormExtras>;
  saving: boolean;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
}

/** Painel da aba ativa. Na criação (sem produto) só existe a aba geral. */
export function ProductFormPainel({
  activeTab,
  produtoParaEditar,
  allProducts,
  campos,
  extras,
  saving,
  onClose,
  onSubmit,
}: ProductFormPainelProps) {
  if (!produtoParaEditar || activeTab === "geral") {
    return (
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
        onSubmit={onSubmit}
      />
    );
  }

  if (activeTab === "estoque") {
    return (
      <ProductFormEstoqueTab
        estoques={extras.estoques}
        cdNome={extras.cdNome}
        cdQtd={extras.cdQtd}
        updatingStock={extras.updatingStock}
        onCdNome={extras.setCdNome}
        onCdQtd={extras.setCdQtd}
        onSalvar={extras.handleSalvarEstoque}
      />
    );
  }

  if (activeTab === "descontos") {
    return (
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
    );
  }

  if (activeTab === "compatibilidades") {
    return (
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
    );
  }

  return null;
}
