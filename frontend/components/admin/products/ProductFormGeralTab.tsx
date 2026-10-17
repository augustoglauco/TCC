"use client";

import React from "react";
import { getApiBaseUrl } from "@/lib/api/apiBaseUrl";
import type { AdminProduct, AdminProductImage } from "@/lib/types/adminProducts";

const inputCls =
  "mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500";

interface ProductFormGeralTabProps {
  produtoParaEditar?: AdminProduct | null;
  nome: string;
  categoria: string;
  preco: string;
  precoBaseFornecedor: string;
  diasAlertaEstoque: string;
  descricao: string;
  especificacoesTecnicas: string;
  imagemPreview: string | null;
  imagens: AdminProductImage[];
  deletingImageId: number | null;
  saving: boolean;
  onNome: (v: string) => void;
  onCategoria: (v: string) => void;
  onPreco: (v: string) => void;
  onPrecoBase: (v: string) => void;
  onDiasAlerta: (v: string) => void;
  onDescricao: (v: string) => void;
  onEspecificacoes: (v: string) => void;
  onImageChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRemoverImagem: (id: number) => void;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
}

export function ProductFormGeralTab({
  produtoParaEditar,
  nome,
  categoria,
  preco,
  precoBaseFornecedor,
  diasAlertaEstoque,
  descricao,
  especificacoesTecnicas,
  imagemPreview,
  imagens,
  deletingImageId,
  saving,
  onNome,
  onCategoria,
  onPreco,
  onPrecoBase,
  onDiasAlerta,
  onDescricao,
  onEspecificacoes,
  onImageChange,
  onRemoverImagem,
  onClose,
  onSubmit,
}: ProductFormGeralTabProps) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="md:col-span-2">
          <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
            Nome do Produto *
          </label>
          <input
            type="text"
            required
            value={nome}
            onChange={(e) => onNome(e.target.value)}
            placeholder="Ex: Gravador IP NVD 1016"
            className={inputCls}
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
            onChange={(e) => onCategoria(e.target.value)}
            placeholder="Ex: CFTV"
            className={inputCls}
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
              onChange={(e) => onPrecoBase(e.target.value)}
              placeholder="R$ 0,00"
              className={inputCls}
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
              onChange={(e) => onPreco(e.target.value)}
              placeholder="R$ 0,00"
              className={`${inputCls} font-semibold text-gray-900`}
            />
          </div>
        </div>

        <div>
          <label
            htmlFor="produto-dias-alerta-estoque"
            className="block text-xs font-semibold text-gray-700 uppercase tracking-wider"
          >
            Alertar estoque com (dias)
          </label>
          <input
            id="produto-dias-alerta-estoque"
            type="number"
            step="1"
            min="1"
            max="365"
            value={diasAlertaEstoque}
            onChange={(e) => onDiasAlerta(e.target.value)}
            placeholder="Padrão do sistema (10)"
            className={inputCls}
          />
          <p className="mt-1 text-[11px] text-gray-500">
            O agente avisa quando a previsão de estoque cair abaixo disto. Use o prazo de
            reposição/entrega deste produto; vazio usa o padrão.
          </p>
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Descrição Comercial
        </label>
        <textarea
          rows={2}
          value={descricao}
          onChange={(e) => onDescricao(e.target.value)}
          placeholder="Descrição do produto para o catálogo e assistente de vendas..."
          className={inputCls}
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider">
          Especificações Técnicas
        </label>
        <textarea
          rows={2}
          value={especificacoesTecnicas}
          onChange={(e) => onEspecificacoes(e.target.value)}
          placeholder="Canais, resolução, alcance IR, voltagem, portas..."
          className={inputCls}
        />
      </div>

      <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-blue-900">
              Foto do Produto &amp; Catálogo Visual CLIP
            </h4>
            <p className="text-xs text-blue-700">
              A imagem é vetorizada automaticamente no Qdrant para reconhecimento por foto no chat.
            </p>
          </div>
          {imagemPreview && (
            <div className="relative h-16 w-16 overflow-hidden rounded-lg border border-gray-200 bg-white">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={imagemPreview} alt="Preview" className="h-full w-full object-cover" />
            </div>
          )}
        </div>

        <div className="mt-3">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={onImageChange}
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
                    className={`group relative h-14 w-14 overflow-hidden rounded border border-gray-200 bg-white ${isDeleting ? "opacity-40" : ""}`}
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
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
                      onClick={() => onRemoverImagem(img.id)}
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
  );
}
