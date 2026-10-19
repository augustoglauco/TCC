"use client";

import React, { useState, useEffect } from "react";
import { useAuthStore } from "@/lib/hooks/useAuthStore";
import { useProductFormCampos } from "@/lib/hooks/useProductFormCampos";
import { useProductFormExtras } from "@/lib/hooks/useProductFormExtras";
import { useProductFormSubmit } from "@/lib/hooks/useProductFormSubmit";
import type { AdminProduct } from "@/lib/types/adminProducts";
import { ProductFormPainel } from "./ProductFormPainel";
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

  const { saving, handleSubmit } = useProductFormSubmit({
    token,
    produtoParaEditar,
    campos,
    onSuccess,
    onClose,
    setError,
  });

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

        <ProductFormPainel
          activeTab={activeTab}
          produtoParaEditar={produtoParaEditar}
          allProducts={allProducts}
          campos={campos}
          extras={extras}
          saving={saving}
          onClose={onClose}
          onSubmit={handleSubmit}
        />
      </div>
    </div>
  );
}
