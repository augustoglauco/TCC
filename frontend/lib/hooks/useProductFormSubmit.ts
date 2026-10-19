"use client";

import React, { useState } from "react";
import {
  createAdminProduct,
  updateAdminProduct,
  uploadAdminProductImage,
} from "@/lib/api/adminProducts";
import { mensagemDeErro } from "@/lib/hooks/useProductFormCampos";
import type { AdminProduct } from "@/lib/types/adminProducts";

export interface CamposParaPayload {
  nome: string;
  categoria: string;
  preco: string;
  precoBaseFornecedor: string;
  diasAlertaEstoque: string;
  descricao: string;
  especificacoesTecnicas: string;
}

export type ResultadoPayload = { payload: Partial<AdminProduct> } | { erro: string };

/** Valida os campos do formulário geral e monta o payload enviado à API. */
export function montarPayloadProduto(campos: CamposParaPayload): ResultadoPayload {
  if (!campos.nome.trim()) return { erro: "O nome do produto é obrigatório." };
  const precoNum = parseFloat(campos.preco);
  if (isNaN(precoNum) || precoNum < 0) return { erro: "Informe um preço de venda válido." };

  return {
    payload: {
      nome: campos.nome.trim(),
      categoria: campos.categoria.trim() || "Geral",
      preco: precoNum,
      preco_base_fornecedor: campos.precoBaseFornecedor
        ? parseFloat(campos.precoBaseFornecedor)
        : null,
      dias_alerta_estoque: campos.diasAlertaEstoque ? parseInt(campos.diasAlertaEstoque, 10) : null,
      descricao: campos.descricao.trim(),
      especificacoes_tecnicas: campos.especificacoesTecnicas.trim() || null,
    },
  };
}

interface SubmitDeps {
  token: string | null;
  produtoParaEditar?: AdminProduct | null;
  campos: CamposParaPayload & { imagemFile: File | null };
  onSuccess: () => void;
  onClose: () => void;
  setError: (msg: string | null) => void;
}

/** Envio do formulário geral: validação, criação/edição e upload da imagem nova. */
export function useProductFormSubmit({
  token,
  produtoParaEditar,
  campos,
  onSuccess,
  onClose,
  setError,
}: SubmitDeps) {
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const resultado = montarPayloadProduto(campos);
    if ("erro" in resultado) {
      setError(resultado.erro);
      return;
    }
    if (!token) return;

    setSaving(true);
    setError(null);
    try {
      const { payload } = resultado;
      const produtoSalvo = produtoParaEditar
        ? await updateAdminProduct(token, produtoParaEditar.id, payload)
        : await createAdminProduct(token, payload);
      if (campos.imagemFile) {
        await uploadAdminProductImage(token, produtoSalvo.id, campos.imagemFile);
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(mensagemDeErro(err, "Erro ao salvar produto"));
    } finally {
      setSaving(false);
    }
  };

  return { saving, handleSubmit };
}
