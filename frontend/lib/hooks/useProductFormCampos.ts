"use client";

import React, { useCallback, useState } from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import { deleteAdminProductImage, fetchAdminProduct } from "@/lib/api/adminProducts";
import type { AdminProduct, AdminProductImage } from "@/lib/types/adminProducts";

export function resolveImageUrl(url?: string | null): string | null {
  if (!url) return null;
  return url.startsWith("http") ? url : `${getApiBaseUrl()}${url}`;
}

export function mensagemDeErro(err: unknown, fallback: string): string {
  return (err instanceof Error && err.message) || fallback;
}

/** Foto escolhida no formulário e ainda não enviada; `chave` é `n:<n>` (as já salvas usam `e:<id>`). */
export interface NovaImagem {
  chave: string;
  file: File;
  preview: string;
}

let proximaChave = 0;

/**
 * Chave da foto padrão: a escolhida pelo admin; senão a que o produto já tem; senão
 * (produto sem foto) a primeira nova — o backend também faz da primeira foto a padrão.
 */
export function chavePrincipalEfetiva(
  escolhida: string | null,
  imagens: AdminProductImage[],
  novas: NovaImagem[],
  urlAtual?: string | null,
): string | null {
  if (escolhida) return escolhida;
  const atual =
    imagens.find((i) => i.imagem_url === urlAtual) ??
    imagens.find((i) => i.is_principal) ??
    imagens[0];
  if (atual) return `e:${atual.id}`;
  return novas[0]?.chave ?? null;
}

function previewDaPrincipal(
  chave: string | null,
  imagens: AdminProductImage[],
  novas: NovaImagem[],
): string | null {
  if (!chave) return null;
  const nova = novas.find((n) => n.chave === chave);
  if (nova) return nova.preview;
  const existente = imagens.find((i) => `e:${i.id}` === chave);
  return resolveImageUrl(existente?.imagem_url);
}

interface RemocaoImagemDeps {
  token: string | null;
  produtoParaEditar?: AdminProduct | null;
  onSuccess: (produtoAtualizado?: AdminProduct) => void;
  setError: (msg: string | null) => void;
}

/** Campos do formulário geral do produto + imagens (arquivo novo, preview e fotos existentes). */
export function useProductFormCampos({
  token,
  produtoParaEditar,
  onSuccess,
  setError,
}: RemocaoImagemDeps) {
  const [nome, setNome] = useState("");
  const [categoria, setCategoria] = useState("CFTV");
  const [familia, setFamilia] = useState("");
  const [preco, setPreco] = useState("");
  const [precoBaseFornecedor, setPrecoBaseFornecedor] = useState("");
  const [diasAlertaEstoque, setDiasAlertaEstoque] = useState("");
  const [descricao, setDescricao] = useState("");
  const [especificacoesTecnicas, setEspecificacoesTecnicas] = useState("");
  const [dimensoesCm, setDimensoesCm] = useState("");
  const [pesoKg, setPesoKg] = useState("");
  const [novasImagens, setNovasImagens] = useState<NovaImagem[]>([]);
  const [principalChave, setPrincipalChave] = useState<string | null>(null);
  const [imagens, setImagens] = useState<AdminProductImage[]>([]);
  const [deletingImageId, setDeletingImageId] = useState<number | null>(null);

  const limparImagens = useCallback(() => {
    setNovasImagens([]);
    setPrincipalChave(null);
    setImagens([]);
  }, []);

  /** Modal fechado: só descarta as imagens (os textos permanecem, como antes). */
  const fechar = limparImagens;

  const novo = useCallback(() => {
    setNome("");
    setCategoria("CFTV");
    setFamilia("");
    setPreco("");
    setPrecoBaseFornecedor("");
    setDiasAlertaEstoque("");
    setDescricao("");
    setEspecificacoesTecnicas("");
    setDimensoesCm("");
    setPesoKg("");
    limparImagens();
  }, [limparImagens]);

  const preencher = useCallback((p: AdminProduct) => {
    setNome(p.nome);
    setCategoria(p.categoria || "Geral");
    setFamilia(p.familia || "");
    setPreco(p.preco ? String(p.preco) : "");
    setPrecoBaseFornecedor(p.preco_base_fornecedor ? String(p.preco_base_fornecedor) : "");
    setDiasAlertaEstoque(p.dias_alerta_estoque ? String(p.dias_alerta_estoque) : "");
    setDescricao(p.descricao || "");
    setEspecificacoesTecnicas(p.especificacoes_tecnicas || "");
    setDimensoesCm(p.dimensoes_cm || "");
    setPesoKg(p.peso_kg ? String(p.peso_kg) : "");
    setImagens(p.imagens || []);
    setNovasImagens([]);
    setPrincipalChave(null);
  }, []);

  /** Uma foto por vez: cada escolha entra na lista, sem trocar a padrão. */
  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const nova = { chave: `n:${proximaChave++}`, file, preview: URL.createObjectURL(file) };
    setNovasImagens((prev) => [...prev, nova]);
    e.target.value = "";
  };

  const handleRemoverNovaImagem = (chave: string) => {
    setNovasImagens((prev) => prev.filter((n) => n.chave !== chave));
    setPrincipalChave((atual) => (atual === chave ? null : atual));
  };

  const chavePadrao = chavePrincipalEfetiva(
    principalChave,
    imagens,
    novasImagens,
    produtoParaEditar?.imagem_url,
  );
  const imagemPreview = previewDaPrincipal(chavePadrao, imagens, novasImagens);

  const handleRemoverImagemExistente = async (imgId: number) => {
    if (!produtoParaEditar || deletingImageId !== null || !token) return;
    setDeletingImageId(imgId);
    setError(null);

    const imagemRemovida = imagens.find((img) => img.id === imgId);
    setImagens(imagens.filter((img) => img.id !== imgId));

    try {
      await deleteAdminProductImage(token, produtoParaEditar.id, imgId);
      setPrincipalChave((atual) => (atual === `e:${imgId}` ? null : atual));
      let produtoAtualizado: AdminProduct | null = null;
      try {
        produtoAtualizado = await fetchAdminProduct(token, produtoParaEditar.id);
        setImagens(produtoAtualizado.imagens || []);
      } catch {
        // Sem o produto atualizado, a lista local (já sem a removida) basta.
      }
      onSuccess(produtoAtualizado || undefined);
    } catch (err) {
      if (imagemRemovida) setImagens((prev) => [...prev, imagemRemovida]);
      setError(mensagemDeErro(err, "Erro ao remover imagem"));
    } finally {
      setDeletingImageId(null);
    }
  };

  return {
    nome,
    categoria,
    familia,
    preco,
    precoBaseFornecedor,
    diasAlertaEstoque,
    descricao,
    especificacoesTecnicas,
    dimensoesCm,
    pesoKg,
    novasImagens,
    chavePadrao,
    imagemPreview,
    imagens,
    deletingImageId,
    setNome,
    setCategoria,
    setFamilia,
    setPreco,
    setPrecoBaseFornecedor,
    setDiasAlertaEstoque,
    setDescricao,
    setEspecificacoesTecnicas,
    setDimensoesCm,
    setPesoKg,
    handleImageChange,
    handleRemoverImagemExistente,
    handleRemoverNovaImagem,
    setPrincipalChave,
    preencher,
    novo,
    fechar,
  };
}
