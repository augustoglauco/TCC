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
  const [preco, setPreco] = useState("");
  const [precoBaseFornecedor, setPrecoBaseFornecedor] = useState("");
  const [diasAlertaEstoque, setDiasAlertaEstoque] = useState("");
  const [descricao, setDescricao] = useState("");
  const [especificacoesTecnicas, setEspecificacoesTecnicas] = useState("");
  const [imagemFile, setImagemFile] = useState<File | null>(null);
  const [imagemPreview, setImagemPreview] = useState<string | null>(null);
  const [imagens, setImagens] = useState<AdminProductImage[]>([]);
  const [deletingImageId, setDeletingImageId] = useState<number | null>(null);

  const limparImagens = useCallback(() => {
    setImagemFile(null);
    setImagemPreview(null);
    setImagens([]);
  }, []);

  /** Modal fechado: só descarta as imagens (os textos permanecem, como antes). */
  const fechar = limparImagens;

  const novo = useCallback(() => {
    setNome("");
    setCategoria("CFTV");
    setPreco("");
    setPrecoBaseFornecedor("");
    setDiasAlertaEstoque("");
    setDescricao("");
    setEspecificacoesTecnicas("");
    limparImagens();
  }, [limparImagens]);

  const preencher = useCallback((p: AdminProduct) => {
    setNome(p.nome);
    setCategoria(p.categoria || "Geral");
    setPreco(p.preco ? String(p.preco) : "");
    setPrecoBaseFornecedor(p.preco_base_fornecedor ? String(p.preco_base_fornecedor) : "");
    setDiasAlertaEstoque(p.dias_alerta_estoque ? String(p.dias_alerta_estoque) : "");
    setDescricao(p.descricao || "");
    setEspecificacoesTecnicas(p.especificacoes_tecnicas || "");
    setImagemPreview(resolveImageUrl(p.imagem_url));
    setImagens(p.imagens || []);
    setImagemFile(null);
  }, []);

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

  return {
    nome,
    categoria,
    preco,
    precoBaseFornecedor,
    diasAlertaEstoque,
    descricao,
    especificacoesTecnicas,
    imagemFile,
    imagemPreview,
    imagens,
    deletingImageId,
    setNome,
    setCategoria,
    setPreco,
    setPrecoBaseFornecedor,
    setDiasAlertaEstoque,
    setDescricao,
    setEspecificacoesTecnicas,
    handleImageChange,
    handleRemoverImagemExistente,
    preencher,
    novo,
    fechar,
  };
}
