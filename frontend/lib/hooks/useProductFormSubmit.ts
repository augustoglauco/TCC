"use client";

import React, { useState } from "react";
import {
  createAdminProduct,
  updateAdminProduct,
  setAdminProductMainImage,
  uploadAdminProductImage,
} from "@/lib/api/adminProducts";
import { mensagemDeErro, type NovaImagem } from "@/lib/hooks/useProductFormCampos";
import type { AdminProduct } from "@/lib/types/adminProducts";

export interface CamposParaPayload {
  nome: string;
  categoria: string;
  familia: string;
  preco: string;
  precoBaseFornecedor: string;
  diasAlertaEstoque: string;
  descricao: string;
  especificacoesTecnicas: string;
  dimensoesCm?: string;
  pesoKg?: string;
}

export type ResultadoPayload = { payload: Partial<AdminProduct> } | { erro: string };

/** Valida os campos do formulário geral e monta o payload enviado à API. */
export function montarPayloadProduto(campos: CamposParaPayload): ResultadoPayload {
  if (!campos.nome.trim()) return { erro: "O nome do produto é obrigatório." };
  const precoNum = parseFloat(campos.preco);
  if (isNaN(precoNum) || precoNum < 0) return { erro: "Informe um preço de venda válido." };
  const pesoNum = campos.pesoKg ? parseFloat(campos.pesoKg.replace(",", ".")) : null;
  if (pesoNum !== null && (isNaN(pesoNum) || pesoNum < 0)) {
    return { erro: "Informe um peso válido (kg)." };
  }

  return {
    payload: {
      nome: campos.nome.trim(),
      categoria: campos.categoria.trim() || "Geral",
      familia: campos.familia.trim() || null,
      preco: precoNum,
      preco_base_fornecedor: campos.precoBaseFornecedor
        ? parseFloat(campos.precoBaseFornecedor)
        : null,
      dias_alerta_estoque: campos.diasAlertaEstoque ? parseInt(campos.diasAlertaEstoque, 10) : null,
      descricao: campos.descricao.trim(),
      especificacoes_tecnicas: campos.especificacoesTecnicas.trim() || null,
      dimensoes_cm: campos.dimensoesCm?.trim() || null,
      peso_kg: pesoNum,
    },
  };
}

/** Envia as fotos novas na ordem escolhida; só a marcada como padrão vira a foto principal. */
export async function enviarImagens(
  token: string,
  produtoId: number,
  novas: NovaImagem[],
  chavePadrao: string | null,
): Promise<void> {
  for (const nova of novas) {
    await uploadAdminProductImage(token, produtoId, nova.file, nova.chave === chavePadrao);
  }
  if (chavePadrao?.startsWith("e:")) {
    await setAdminProductMainImage(token, produtoId, Number(chavePadrao.slice(2)));
  }
}

interface SubmitDeps {
  token: string | null;
  produtoParaEditar?: AdminProduct | null;
  campos: CamposParaPayload & { novasImagens: NovaImagem[]; chavePadrao: string | null };
  onSuccess: () => void;
  onClose: () => void;
  setError: (msg: string | null) => void;
}

/** Envio do formulário geral: validação, criação/edição e upload das fotos novas e da foto padrão. */
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
      await enviarImagens(token, produtoSalvo.id, campos.novasImagens, campos.chavePadrao);
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
